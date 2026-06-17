"""Unit tests for the profile cache logic in browser_manager.
No real Chrome or disk I/O beyond tmp_path — all Chrome paths are monkeypatched."""
import json
import shutil
import time
from pathlib import Path

import pytest

import scraper.browser_manager as bm
from scraper.browser_manager import (
    ProfileCopyError,
    _get_cookies_mtime,
    _is_cache_valid,
    _read_cache_meta,
    _write_cache_meta,
    copy_profile_snapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source_profile(base: Path, profile_name: str = "Default") -> Path:
    """Create a minimal fake Chrome user_data_dir with a Cookies file."""
    user_data = base / "User Data"
    profile_dir = user_data / profile_name
    profile_dir.mkdir(parents=True)
    (profile_dir / "Cookies").write_bytes(b"fake-cookies")
    (profile_dir / "Preferences").write_bytes(b"{}")
    local_state = {"profile": {"last_used": profile_name}}
    (user_data / "Local State").write_text(json.dumps(local_state), encoding="utf-8")
    return user_data


def _patch_chrome(monkeypatch, user_data_dir: Path) -> None:
    monkeypatch.setattr(bm, "get_chrome_user_data_dir", lambda: user_data_dir)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_cache_miss_on_first_run(tmp_path, monkeypatch):
    user_data = _make_source_profile(tmp_path)
    _patch_chrome(monkeypatch, user_data)

    cache_root = tmp_path / "cache"
    result = copy_profile_snapshot(dest_root=cache_root)

    assert result == cache_root
    assert (cache_root / "Default" / "Cookies").exists()
    meta = _read_cache_meta(cache_root)
    assert meta is not None
    assert meta["profile_name"] == "Default"
    assert isinstance(meta["cookies_mtime"], float)


def test_cache_hit_skips_copy(tmp_path, monkeypatch):
    user_data = _make_source_profile(tmp_path)
    _patch_chrome(monkeypatch, user_data)
    cache_root = tmp_path / "cache"

    copy_profile_snapshot(dest_root=cache_root)

    # Track whether _copy_tree_best_effort is called on second invocation
    copy_calls = []
    original = bm._copy_tree_best_effort

    def spy(src, dst):
        copy_calls.append((src, dst))
        return original(src, dst)

    monkeypatch.setattr(bm, "_copy_tree_best_effort", spy)
    copy_profile_snapshot(dest_root=cache_root)

    assert copy_calls == [], "Full copy should not run on a cache hit"


def test_cache_invalidated_when_cookies_mtime_changes(tmp_path, monkeypatch):
    user_data = _make_source_profile(tmp_path)
    _patch_chrome(monkeypatch, user_data)
    cache_root = tmp_path / "cache"

    copy_profile_snapshot(dest_root=cache_root)

    # Touch the Cookies file to advance its mtime
    cookies_path = user_data / "Default" / "Cookies"
    time.sleep(0.01)  # ensure mtime differs
    cookies_path.write_bytes(b"updated-cookies")

    copy_calls = []
    original = bm._copy_tree_best_effort

    def spy(src, dst):
        copy_calls.append(src)
        return original(src, dst)

    monkeypatch.setattr(bm, "_copy_tree_best_effort", spy)
    copy_profile_snapshot(dest_root=cache_root)

    assert len(copy_calls) == 1, "Re-copy must run when Cookies mtime changes"


def test_cache_invalidated_when_profile_name_changes(tmp_path, monkeypatch):
    user_data = _make_source_profile(tmp_path, profile_name="Default")
    _patch_chrome(monkeypatch, user_data)
    cache_root = tmp_path / "cache"

    copy_profile_snapshot(dest_root=cache_root)

    # Simulate user switching to Profile 1
    new_profile_dir = user_data / "Profile 1"
    new_profile_dir.mkdir(parents=True)
    (new_profile_dir / "Cookies").write_bytes(b"profile1-cookies")
    local_state = {"profile": {"last_used": "Profile 1"}}
    (user_data / "Local State").write_text(json.dumps(local_state), encoding="utf-8")

    copy_calls = []
    original = bm._copy_tree_best_effort

    def spy(src, dst):
        copy_calls.append(src)
        return original(src, dst)

    monkeypatch.setattr(bm, "_copy_tree_best_effort", spy)
    copy_profile_snapshot(dest_root=cache_root)

    assert len(copy_calls) == 1, "Re-copy must run when profile name changes"


def test_cache_invalid_if_default_dir_missing(tmp_path):
    # Chrome locks the Cookies file so it may not be copied — we only require
    # the Default/ directory itself to exist, not any specific file inside it.
    cache_root = tmp_path / "cache"
    cache_root.mkdir(parents=True)
    _write_cache_meta(cache_root, "Default", 1234567890.0)
    # Default/ dir is absent → cache is invalid

    assert not _is_cache_valid(cache_root, "Default", 1234567890.0)


def test_local_state_refreshed_on_cache_hit(tmp_path, monkeypatch):
    user_data = _make_source_profile(tmp_path)
    _patch_chrome(monkeypatch, user_data)
    cache_root = tmp_path / "cache"

    copy_profile_snapshot(dest_root=cache_root)

    copy2_calls = []
    original_copy2 = shutil.copy2

    def spy_copy2(src, dst, **kwargs):
        copy2_calls.append(Path(src).name)
        return original_copy2(src, dst, **kwargs)

    monkeypatch.setattr(shutil, "copy2", spy_copy2)
    copy_profile_snapshot(dest_root=cache_root)

    assert "Local State" in copy2_calls, "Local State must be re-copied on cache hit"


def test_staging_cleaned_up_on_copy_error(tmp_path, monkeypatch):
    user_data = _make_source_profile(tmp_path)
    _patch_chrome(monkeypatch, user_data)
    cache_root = tmp_path / "cache"

    monkeypatch.setattr(bm, "_copy_tree_best_effort", lambda src, dst: (_ for _ in ()).throw(OSError("disk full")))

    with pytest.raises(ProfileCopyError):
        copy_profile_snapshot(dest_root=cache_root)

    staging_dir = cache_root.parent / (cache_root.name + "_staging")
    assert not staging_dir.exists(), "Staging dir must be cleaned up after failed copy"


def test_network_cookies_fallback(tmp_path):
    """Chrome 96+ may store cookies under Network/Cookies instead of root Cookies."""
    profile_dir = tmp_path / "profile"
    network_dir = profile_dir / "Network"
    network_dir.mkdir(parents=True)
    (network_dir / "Cookies").write_bytes(b"network-cookies")
    # No top-level Cookies file

    mtime = _get_cookies_mtime(profile_dir)
    assert mtime is not None
    assert isinstance(mtime, float)
