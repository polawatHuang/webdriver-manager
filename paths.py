"""Runtime path resolution that works both from source and from a frozen PyInstaller build."""
import sys
from pathlib import Path


def get_app_base_dir() -> Path:
    """Directory the .exe lives in (onedir build), or the project dir in source mode.

    Deliberately NOT sys._MEIPASS — that is an ephemeral extraction temp dir that
    does not persist across runs, so it is wrong for anything that must survive
    between launches (logs, the ms-playwright sibling folder).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_logs_dir() -> Path:
    d = get_app_base_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_default_export_dir() -> Path:
    return Path.home() / "Documents" / "TOA Lucky Draw Exports"


def get_browsers_dir() -> Path:
    """Sibling 'ms-playwright' folder shipped next to the exe (onedir packaging)."""
    return get_app_base_dir() / "ms-playwright"


def resource_path(relative: str) -> Path:
    """Read-only bundled assets (logo, icon, sounds)."""
    base = Path(getattr(sys, "_MEIPASS", get_app_base_dir()))
    return base / relative
