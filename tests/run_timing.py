"""Timing smoke-test for profile copy cache.
Run from project root: python tests/run_timing.py

First call does a full copy (cold); second call should hit the cache and be near-instant.
"""
import json
import sys
import time
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import scraper.browser_manager as bm
from scraper.browser_manager import (
    _get_cookies_mtime,
    _get_last_used_profile_name,
    _is_cache_valid,
    _read_cache_meta,
    copy_profile_snapshot,
    get_chrome_user_data_dir,
)

dest = Path(tempfile.mkdtemp(prefix="toa_timing_"))
print(f"Cache root: {dest}")

print("\nCold copy (first run)...")
t0 = time.perf_counter()
copy_profile_snapshot(dest_root=dest)
cold = time.perf_counter() - t0
print(f"  Cold: {cold:.2f}s")

# Diagnose cache state before warm call
user_data_dir = get_chrome_user_data_dir()
profile_name = _get_last_used_profile_name(user_data_dir)
source_profile_dir = user_data_dir / profile_name
mtime = _get_cookies_mtime(source_profile_dir)

print(f"\nDiagnostics:")
print(f"  profile_name        : {profile_name!r}")
print(f"  source_cookies_mtime: {mtime}")
print(f"  cache_root exists   : {dest.exists()}")
print(f"  Default/ exists     : {(dest / 'Default').exists()}")
meta = _read_cache_meta(dest)
print(f"  cache_meta.json     : {meta}")
if meta and mtime is not None:
    print(f"  profile_name match  : {meta['profile_name'] == profile_name}")
    print(f"  mtime match         : {meta['cookies_mtime'] == mtime}")
    print(f"  stored mtime        : {repr(meta['cookies_mtime'])}")
    print(f"  current mtime       : {repr(mtime)}")
    print(f"  diff                : {meta['cookies_mtime'] - mtime}")
print(f"  _is_cache_valid     : {_is_cache_valid(dest, profile_name, mtime)}")

print("\nWarm copy (cache hit)...")
t0 = time.perf_counter()
copy_profile_snapshot(dest_root=dest)
warm = time.perf_counter() - t0
print(f"  Warm: {warm:.2f}s")

speedup = cold / warm if warm > 0 else float("inf")
print(f"\nSpeedup: {speedup:.0f}x  (target: warm < 2.0s)")

if warm >= 2.0:
    print(f"FAIL: warm copy took {warm:.2f}s, expected < 2.0s")
    sys.exit(1)
else:
    print("PASS")
