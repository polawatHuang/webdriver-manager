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
    "VideoDecodeStats", "optimization_guide*",
    "shared_proto_db", "BudgetDatabase",
    # Extension state is not needed
    "Local Extension Settings",
    # Crash + log artefacts
    "CrashpadMetrics*", "*.log",
)


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


def copy_profile_snapshot(dest_root: Path | None = None) -> Path:
    """Copies the active Chrome profile subfolder into a fresh temp dir and
    returns that path for use as Playwright's user_data_dir."""
    user_data_dir = get_chrome_user_data_dir()
    profile_name = _get_last_used_profile_name(user_data_dir)
    source_profile_dir = user_data_dir / profile_name

    if not source_profile_dir.exists():
        raise ProfileCopyError(f"Chrome profile not found: {source_profile_dir}")

    dest_root = dest_root or Path(tempfile.mkdtemp(prefix="toa_lucky_draw_profile_"))
    dest_profile_dir = dest_root / "Default"

    try:
        _copy_tree_best_effort(source_profile_dir, dest_profile_dir)
        # Playwright reads Local State (for things like the dictionary of installed
        # extensions/encryption keys) from the user_data_dir root, not the profile dir.
        local_state_src = user_data_dir / "Local State"
        if local_state_src.exists():
            shutil.copy2(local_state_src, dest_root / "Local State")
    except (OSError, shutil.Error) as exc:
        logger.exception("Failed to copy Chrome profile")
        raise ProfileCopyError(str(exc)) from exc

    logger.info("Copied Chrome profile '%s' to %s", profile_name, dest_root)
    return dest_root


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
