from __future__ import annotations

import json
from pathlib import Path

import xbmc
import xbmcgui
import xbmcvfs

from ..app_title import app_title
from ..paths import userdata_dir
from ..platforms import get_platform
from .http_client import download_bytes
from .providers import (
    PLATFORM_ART_SCREENSCRAPER,
    PLATFORM_ART_STEAMGRIDDB,
    platform_art_provider,
    steamgriddb_api_key,
)
from .screenscraper import credentials_configured, fetch_system_logo, validate_credentials
from .steamgriddb import fetch_icon, search_autocomplete_all, validate_api_key

APP_NAME = app_title()

PLATFORM_SGDB_QUERIES: dict[str, str] = {
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


def _map_path() -> Path:
    return userdata_dir() / "platform_art_map.json"


def _load_map() -> dict[str, dict]:
    path = _map_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_map(data: dict[str, dict]) -> None:
    _map_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _cached_path(platform_id: str) -> Path:
    return platform_art_dir() / f"{platform_id}.png"


def _platform_query(platform_id: str) -> str:
    platform = get_platform(platform_id)
    return PLATFORM_SGDB_QUERIES.get(platform_id) or (platform.name if platform else platform_id)


def _result_label(item: dict) -> str:
    name = str(item.get("name") or item.get("title") or "Unknown")
    item_id = item.get("id")
    item_type = str(item.get("type") or item.get("types") or "").strip()
    if item_type:
        return f"{name} ({item_type}) [#{item_id}]"
    return f"{name} [#{item_id}]"


def pick_platform_sgdb_match(platform_id: str) -> dict | None:
    api_key = steamgriddb_api_key()
    if not api_key or not validate_api_key(api_key):
        xbmcgui.Dialog().ok(
            APP_NAME,
            "Set a valid SteamGridDB API key under Games settings → Metadata.",
        )
        return None
    query = _platform_query(platform_id)
    results = search_autocomplete_all(query, api_key, limit=30)
    if not results:
        xbmcgui.Dialog().notification(
            APP_NAME,
            f"No SteamGridDB matches for {query}",
            xbmcgui.NOTIFICATION_WARNING,
            3500,
        )
        return None
    labels = [_result_label(item) for item in results]
    platform = get_platform(platform_id)
    heading = f"Choose SteamGridDB art for {platform.name if platform else platform_id}"
    index = xbmcgui.Dialog().select(heading, labels)
    if index < 0:
        return None
    return results[index]


def save_platform_art(platform_id: str, sgdb_match: dict) -> str:
    api_key = steamgriddb_api_key()
    sgdb_id = int(sgdb_match["id"])
    asset = fetch_icon(sgdb_id, api_key)
    if not asset or not asset.get("url"):
        raise RuntimeError("No icon or grid art found on SteamGridDB for that entry")
    dest = _cached_path(platform_id)
    dest.write_bytes(download_bytes(asset["url"]))
    mapping = _load_map()
    mapping[platform_id] = {
        "provider": PLATFORM_ART_STEAMGRIDDB,
        "sgdb_id": sgdb_id,
        "name": sgdb_match.get("name") or sgdb_match.get("title") or "",
    }
    _save_map(mapping)
    return str(dest)


def choose_platform_art(platform_id: str) -> str:
    match = pick_platform_sgdb_match(platform_id)
    if not match:
        return ""
    try:
        path = save_platform_art(platform_id, match)
        xbmcgui.Dialog().notification(APP_NAME, "Platform artwork saved", xbmcgui.NOTIFICATION_INFO, 2500)
        return path
    except Exception as exc:
        xbmcgui.Dialog().ok(APP_NAME, str(exc))
        return ""


def get_platform_art_path(platform_id: str, *, allow_fetch: bool = True, interactive: bool = False) -> str:
    provider = platform_art_provider()
    if provider == "badge":
        return ""

    cached = _cached_path(platform_id)
    if cached.exists() and xbmcvfs.exists(str(cached)):
        return str(cached)

    if not allow_fetch:
        return ""

    mapping = _load_map()
    if provider == PLATFORM_ART_STEAMGRIDDB:
        api_key = steamgriddb_api_key()
        if not api_key:
            return ""
        entry = mapping.get(platform_id) or {}
        if entry.get("sgdb_id") and validate_api_key(api_key):
            try:
                asset = fetch_icon(int(entry["sgdb_id"]), api_key)
                if asset and asset.get("url"):
                    cached.write_bytes(download_bytes(asset["url"]))
                    return str(cached)
            except Exception as exc:
                xbmc.log(f"[Games] cached SGDB platform art failed {platform_id}: {exc}", xbmc.LOGWARNING)
        if interactive:
            return choose_platform_art(platform_id)
        return ""

    if provider == PLATFORM_ART_SCREENSCRAPER and credentials_configured() and validate_credentials():
        try:
            url = fetch_system_logo(platform_id)
            if not url:
                return ""
            cached.write_bytes(download_bytes(url))
            return str(cached)
        except Exception as exc:
            xbmc.log(f"[Games] platform art fetch failed {platform_id}: {exc}", xbmc.LOGWARNING)
    return ""
