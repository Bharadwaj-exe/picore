"""User settings and secrets.

For word questions the app uses a proxy URL (PICORE_WOLFRAM_PROXY / "wolfram_proxy_url",
preferred for releases, see proxy/) or a Wolfram|Alpha AppID, looked up in order from:
  1. the PICORE_WOLFRAM_APPID environment variable
  2. config.json in the user data folder
  3. picore.config.json next to the app (git-ignored, for development)
"""
import json
import os

from .paths import app_root, user_data_dir

DEFAULTS = {"music_on": True, "wolfram_app_id": "", "wolfram_proxy_url": ""}


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class Settings:
    def __init__(self):
        self.path = user_data_dir() / "config.json"
        self.data = dict(DEFAULTS)
        self.data.update(_read(app_root() / "picore.config.json"))
        self.data.update(_read(self.path))

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        saved = _read(self.path)
        saved[key] = value
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(saved, f, indent=2)
        except OSError:
            pass

    @property
    def wolfram_app_id(self):
        return os.environ.get("PICORE_WOLFRAM_APPID") or self.get("wolfram_app_id") or None

    @property
    def wolfram_proxy(self):
        return os.environ.get("PICORE_WOLFRAM_PROXY") or self.get("wolfram_proxy_url") or None
