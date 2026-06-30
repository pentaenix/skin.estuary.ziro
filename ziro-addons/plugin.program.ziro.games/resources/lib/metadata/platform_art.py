from __future__ import annotations

from pathlib import Path

import xbmc
import xbmcvfs

from ..paths import userdata_dir
from .http_client import download_bytes
from .screenscraper import credentials_configured, fetch_system_logo, validate_credentials

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")


def platform_art_dir() -> Path:
    path = userdata_dir() / "platform_art"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cached_path(platform_id: str) -> Path:
    return platform_art_dir() / f"{platform_id}.png"


def get_platform_art_path(platform_id: str, *, allow_fetch: bool = True) -> str:
    cached = _cached_path(platform_id)
    if cached.exists() and xbmcvfs.exists(str(cached)):
        return str(cached)

    if not allow_fetch or not credentials_configured():
        return ""

    if not validate_credentials():
        return ""

    try:
        url = fetch_system_logo(platform_id)
        if not url:
            return ""
        cached.write_bytes(download_bytes(url))
        return str(cached)
    except Exception as exc:
        xbmc.log(f"[Ziro Games] platform art fetch failed {platform_id}: {exc}", xbmc.LOGWARNING)
        return ""
