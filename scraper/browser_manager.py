"""Chrome detection + profile session reuse for Playwright, without touching the
user's live Chrome window (we copy their profile rather than closing/relaunching it)."""
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

import psutil
from playwright.sync_api import BrowserContext, Page, sync_playwright

from config import HEADLESS

logger = logging.getLogger(__name__)

_IGNORE_PATTERNS = shutil.ignore_patterns(
    # Lock / singleton files that must not be shared
    "Singleton*", "lockfile", "*.lock",
    # Caches — safe to omit, browser rebuilds them on demand
    "Cache", "Cache_Data", "Code Cache", "GPUCache",
    "GrShaderCache", "ShaderCache",
    # Heavy on-disk stores not needed for Facebook login
    "Service Worker", "CacheStorage",
    "blob_storage", "databases",
    "IndexedDB",
    "VideoDecodeStats", "optimization_guide*",
    "shared_proto_db", "BudgetDatabase",
    # Extension state is not needed
    "Local Extension Settings",
    # Crash + log artefacts
    "CrashpadMetrics*", "*.log",
)

_CACHE_META_FILENAME = "cache_meta.json"


class ChromeNotRunningError(Exception):
    """Chrome does not appear to be running."""


class ProfileCopyError(Exception):
    """Could not copy the Chrome profile to a working directory."""


class BrowserLaunchError(Exception):
    """Playwright could not launch a browser (Chrome missing or misconfigured)."""


def is_chrome_running() -> bool:
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if name in ("chrome.exe", "chrome"):
            return True
    return False


def get_chrome_user_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise ChromeNotRunningError("LOCALAPPDATA is not set")
    return Path(local_app_data) / "Google" / "Chrome" / "User Data"


def _get_last_used_profile_name(user_data_dir: Path) -> str:
    """Reads Local State's profile.last_used so multi-profile Chrome users still
    get the profile that's actually logged into Facebook, not a hard-coded 'Default'."""
    local_state_path = user_data_dir / "Local State"
    try:
        data = json.loads(local_state_path.read_text(encoding="utf-8"))
        last_used = data.get("profile", {}).get("last_used")
        if last_used:
            return last_used
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read Local State for last-used profile: %s", exc)
    return "Default"


def _copy_tree_best_effort(src: Path, dst: Path) -> None:
    def _copy_function(s, d):
        try:
            shutil.copy2(s, d)
        except (PermissionError, OSError) as exc:
            logger.debug("Skipping locked/unreadable file %s: %s", s, exc)

    shutil.copytree(
        src,
        dst,
        ignore=_IGNORE_PATTERNS,
        copy_function=_copy_function,
        dirs_exist_ok=True,
    )


def _get_cookies_mtime(source_profile_dir: Path) -> float | None:
    """Returns the max mtime of Cookies / Network/Cookies, or None if neither exists."""
    candidates = [
        source_profile_dir / "Cookies",
        source_profile_dir / "Network" / "Cookies",
    ]
    mtimes = [p.stat().st_mtime for p in candidates if p.exists()]
    return max(mtimes) if mtimes else None


def _read_cache_meta(cache_root: Path) -> dict | None:
    try:
        data = json.loads(
            (cache_root / _CACHE_META_FILENAME).read_text(encoding="utf-8")
        )
        if isinstance(data.get("profile_name"), str) and isinstance(
            data.get("cookies_mtime"), float
        ):
            return data
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    return None


def _write_cache_meta(
    cache_root: Path, profile_name: str, cookies_mtime: float
) -> None:
    (cache_root / _CACHE_META_FILENAME).write_text(
        json.dumps({"profile_name": profile_name, "cookies_mtime": cookies_mtime}),
        encoding="utf-8",
    )


def _is_cache_valid(
    cache_root: Path, profile_name: str, source_cookies_mtime: float | None
) -> bool:
    if source_cookies_mtime is None or not cache_root.exists():
        return False
    # Sanity-check that at least the Default profile dir was created.
    # We do NOT require Default/Cookies to exist: Chrome holds an exclusive
    # lock on that file while running, so _copy_tree_best_effort silently skips
    # it.  cache_meta.json is written only after a successful copy, so it is
    # the authoritative freshness signal.
    if not (cache_root / "Default").exists():
        return False
    meta = _read_cache_meta(cache_root)
    return (
        meta is not None
        and meta["profile_name"] == profile_name
        and meta["cookies_mtime"] == source_cookies_mtime
    )


def copy_profile_snapshot(dest_root: Path | None = None) -> Path:
    """Returns a writable copy of the active Chrome profile for Playwright.

    On the first call (or after the Cookies file changes), performs a full copy
    and caches the result at a stable path.  Subsequent calls with an unchanged
    Cookies file skip the copy entirely and return the cached path in ~0.5 s.

    Args:
        dest_root: Override the cache root (used in tests). If None, uses the
                   app's stable profile_cache directory.
    """
    from paths import get_profile_cache_dir  # local import avoids circular import

    user_data_dir = get_chrome_user_data_dir()
    profile_name = _get_last_used_profile_name(user_data_dir)
    source_profile_dir = user_data_dir / profile_name

    if not source_profile_dir.exists():
        raise ProfileCopyError(f"Chrome profile not found: {source_profile_dir}")

    cache_root = dest_root or get_profile_cache_dir()
    source_cookies_mtime = _get_cookies_mtime(source_profile_dir)

    if _is_cache_valid(cache_root, profile_name, source_cookies_mtime):
        logger.info("Profile cache hit — reusing %s", cache_root)
        # Always refresh Local State on hit: may contain rotated encryption keys.
        local_state_src = user_data_dir / "Local State"
        if local_state_src.exists():
            try:
                shutil.copy2(local_state_src, cache_root / "Local State")
            except OSError as exc:
                logger.warning("Could not refresh Local State in cache: %s", exc)
        return cache_root

    logger.info("Profile cache miss — copying profile '%s'", profile_name)

    # Copy to a staging dir first; rename to cache_root atomically on success.
    # Prevents a partial copy from being treated as valid on the next run.
    cache_root.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = cache_root.parent / (cache_root.name + "_staging")
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)

    try:
        _copy_tree_best_effort(source_profile_dir, staging_dir / "Default")
        local_state_src = user_data_dir / "Local State"
        if local_state_src.exists():
            shutil.copy2(local_state_src, staging_dir / "Local State")
        if source_cookies_mtime is not None:
            _write_cache_meta(staging_dir, profile_name, source_cookies_mtime)
        if cache_root.exists():
            shutil.rmtree(cache_root, ignore_errors=True)
        staging_dir.rename(cache_root)
    except (OSError, shutil.Error) as exc:
        logger.exception("Failed to copy Chrome profile")
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise ProfileCopyError(str(exc)) from exc

    # One-time cleanup of old mkdtemp-style leftovers from before this change.
    for old in Path(tempfile.gettempdir()).glob("toa_lucky_draw_profile_*"):
        shutil.rmtree(old, ignore_errors=True)

    logger.info("Copied and cached Chrome profile '%s' to %s", profile_name, cache_root)
    return cache_root


class PlaywrightSession:
    """Context manager wrapping a Playwright persistent context against a copied
    Chrome profile, so the scraper reuses the user's existing Facebook login."""

    def __init__(self, profile_dir: Path, headless: bool = HEADLESS):
        self.profile_dir = profile_dir
        self.headless = headless
        self._playwright = None
        self._context: BrowserContext | None = None

    def __enter__(self) -> Page:
        self._playwright = sync_playwright().start()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            # Chrome 136+ blocks remote debugging on default profiles without this flag.
            "--disable-features=DevToolsDebuggingRestrictions",
        ]
        try:
            # Use the user's installed Google Chrome instead of Playwright's downloaded
            # Chromium binary — avoids "Executable doesn't exist" when ms-playwright
            # isn't bundled or is out of sync with the Playwright driver version.
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=self.headless,
                channel="chrome",
                viewport={"width": 1280, "height": 1600},
                args=launch_args,
                locale="th-TH",
            )
        except Exception as exc:
            logger.exception("Failed to launch Chrome via Playwright")
            raise BrowserLaunchError(str(exc)) from exc
        page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return page

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._context is not None:
            self._context.close()
        if self._playwright is not None:
            self._playwright.stop()
