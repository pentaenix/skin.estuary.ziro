from __future__ import annotations

from pathlib import Path

import xbmc
import xbmcaddon
import xbmcvfs

from ..paths import userdata_dir
from .http_client import download_bytes, normalize_api_key
from .steamgriddb import fetch_grid, search_game

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")

# Search terms that tend to resolve to SGDB platform entities.
PLATFORM_SEARCH: dict[str, str] = {
    "nes": "Nintendo Entertainment System",
    "snes": "Super Nintendo",
    "n64": "Nintendo 64",
    "gb": "Game Boy",
    "gbc": "Game Boy Color",
    "gba": "Game Boy Advance",
    "nds": "Nintendo DS",
    "3ds": "Nintendo 3DS",
    "gamecube": "Nintendo GameCube",
    "wii": "Nintendo Wii",
    "wiiu": "Nintendo Wii U",
    "switch": "Nintendo Switch",
    "sms": "Sega Master System",
    "genesis": "Sega Genesis",
    "segacd": "Sega CD",
    "saturn": "Sega Saturn",
    "dreamcast": "Sega Dreamcast",
    "ps1": "PlayStation",
    "ps2": "PlayStation 2",
    "ps3": "PlayStation 3",
    "psp": "PlayStation Portable",
    "psvita": "PlayStation Vita",
    "ps4": "PlayStation 4",
    "xbox": "Xbox",
    "xbox360": "Xbox 360",
    "xboxone": "Xbox One",
    "xboxseries": "Xbox Series X",
}


def platform_art_dir() -> Path:
    path = userdata_dir() / "platform_art"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cached_path(platform_id: str) -> Path:
    return platform_art_dir() / f"{platform_id}.jpg"


def get_platform_art_path(platform_id: str, *, allow_fetch: bool = True) -> str:
    cached = _cached_path(platform_id)
    if cached.exists() and xbmcvfs.exists(str(cached)):
        return str(cached)

    if not allow_fetch:
        return ""

    api_key = normalize_api_key(ADDON.getSetting("steamgriddb_api_key") or "")
    if not api_key:
        return ""

    query = PLATFORM_SEARCH.get(platform_id, platform_id)
    try:
        match = search_game(query, api_key)
        if not match:
            return ""
        grid = fetch_grid(int(match["id"]), api_key)
        if not grid or not grid.get("url"):
            return ""
        cached.write_bytes(download_bytes(grid["url"]))
        return str(cached)
    except Exception as exc:
        xbmc.log(f"[Ziro Games] platform art fetch failed {platform_id}: {exc}", xbmc.LOGWARNING)
        return ""
