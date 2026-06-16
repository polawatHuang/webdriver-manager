# PyInstaller spec — onedir build (see README for why this is onedir, not onefile:
# Playwright's Chromium binary can't be reliably embedded in a true single-file exe).
#
# Build with:  pyinstaller build.spec
# Output:      dist/TOA Lucky Draw Collector/TOA Lucky Draw Collector.exe
#
# After building, copy the Chromium folder from your build machine's
# %LOCALAPPDATA%\ms-playwright\chromium-<version> into
# dist/TOA Lucky Draw Collector/ms-playwright/chromium-<version>/
# so the app can find the browser binary at runtime without any setup step.

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("assets", "assets"),
    ],
    hiddenimports=["playwright.sync_api"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TOA Lucky Draw Collector",
    icon="assets/icon.ico",
    console=False,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="TOA Lucky Draw Collector",
)
