"""Locate bundled assets and the per-user data folder (works when frozen)."""
import os
import sys
from pathlib import Path

APP_NAME = "PiCore"


def app_root():
    """Folder holding bundled files: PyInstaller's temp dir, or the project root."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def asset(name):
    return str(app_root() / "assets" / name)


def user_data_dir():
    try:
        from platformdirs import user_data_dir as _udd
        path = Path(_udd(APP_NAME, appauthor=False))
    except ImportError:
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path
