from __future__ import annotations

from pathlib import Path

import xbmc
import xbmcaddon
import xbmcvfs

ADDON_ID = "plugin.program.ziro.games"
ADDON = xbmcaddon.Addon(ADDON_ID)


def translate(path: str) -> str:
    return xbmcvfs.translatePath(path)


def userdata_dir() -> Path:
    path = Path(translate(f"special://profile/addon_data/{ADDON_ID}"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return userdata_dir() / "games.db"


def artwork_dir() -> Path:
    path = userdata_dir() / "artwork"
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_path() -> Path:
    return userdata_dir() / "session.json"
