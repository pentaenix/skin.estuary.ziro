from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import xbmc
import xbmcaddon

from ..db import GameDatabase
from ..paths import artwork_dir
from .http_client import download_bytes
from .providers import steamgriddb_api_key
from .steamgriddb import fetch_grid, fetch_hero, fetch_logo, validate_api_key

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")


def _extension_from_url(url: str, fallback: str = ".png") -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return suffix
    return fallback


def _artwork_path(game_id: int, kind: str, url: str) -> Path:
    return artwork_dir() / str(game_id) / f"{kind}{_extension_from_url(url)}"


def _save_image(url: str, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(download_bytes(url))
    return str(dest)


def enrich_game_sgdb(
    db: GameDatabase,
    game_id: int,
    game: dict,
    *,
    sgdb_match: dict | None = None,
    verify_key: bool = True,
) -> tuple[dict, int | None]:
    api_key = steamgriddb_api_key()
    if not api_key:
        raise RuntimeError("SteamGridDB API key is not set")
    if verify_key and not validate_api_key(api_key):
        raise RuntimeError("SteamGridDB API key is invalid")

    sgdb_game_id = game.get("sgdb_game_id")
    if sgdb_match:
        sgdb_game_id = int(sgdb_match["id"])
    elif not sgdb_game_id:
        from .steamgriddb import search_game

        match = search_game(game["title"], api_key)
        if not match:
            raise RuntimeError(f"No SteamGridDB match for '{game['title']}'")
        sgdb_game_id = int(match["id"])
    else:
        sgdb_game_id = int(sgdb_game_id)

    updates: dict = {
        "sgdb_game_id": sgdb_game_id,
        "metadata_updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    grid = fetch_grid(sgdb_game_id, api_key)
    if not grid or not grid.get("url"):
        raise RuntimeError(f"No grid artwork on SteamGridDB for '{game['title']}'")

    updates["cover_path"] = _save_image(grid["url"], _artwork_path(game_id, "poster", grid["url"]))

    if ADDON.getSettingBool("metadata_fetch_fanart"):
        hero = fetch_hero(sgdb_game_id, api_key)
        if hero and hero.get("url"):
            updates["fanart_path"] = _save_image(hero["url"], _artwork_path(game_id, "fanart", hero["url"]))

    if ADDON.getSettingBool("metadata_fetch_logos"):
        logo = fetch_logo(sgdb_game_id, api_key)
        if logo and logo.get("url"):
            updates["logo_path"] = _save_image(logo["url"], _artwork_path(game_id, "logo", logo["url"]))

    db.update_game_artwork(game_id, updates)
    return updates, sgdb_game_id
