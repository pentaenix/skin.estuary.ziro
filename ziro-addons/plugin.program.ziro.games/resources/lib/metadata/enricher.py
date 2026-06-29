from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import xbmc
import xbmcaddon
import xbmcvfs

from ..db import GameDatabase
from ..paths import artwork_dir
from .http_client import download_bytes
from .steamgriddb import fetch_grid, fetch_hero, fetch_logo, search_game, validate_api_key

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")
REQUEST_DELAY_SEC = 0.4


@dataclass
class ArtworkResult:
    game_id: int
    title: str
    status: str
    message: str = ""
    sgdb_game_id: int | None = None


@dataclass
class ArtworkBatchResult:
    processed: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[ArtworkResult] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "Artwork fetch complete.",
            f"Updated: {self.updated}",
            f"Skipped: {self.skipped}",
            f"Failed: {self.failed}",
        ]
        api_errors = [result for result in self.results if result.status == "api_error"]
        if api_errors:
            sample = api_errors[0].message or "SteamGridDB request failed"
            lines.append("")
            lines.append(f"API error: {sample[:220]}")
            lines.append("Full URLs and response bodies:")
            lines.append("addon_data/plugin.program.ziro.games/sgdb.log")
        return "\n".join(lines)


ProgressCallback = Callable[[int, str], bool]


def _api_key() -> str:
    from .http_client import normalize_api_key

    return normalize_api_key(ADDON.getSetting("steamgriddb_api_key") or "")


def _fetch_fanart() -> bool:
    return ADDON.getSettingBool("metadata_fetch_fanart")


def _fetch_logos() -> bool:
    return ADDON.getSettingBool("metadata_fetch_logos")


def _debug() -> bool:
    return ADDON.getSettingBool("debug_logging")


def _extension_from_url(url: str, fallback: str = ".png") -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return suffix
    return fallback


def _artwork_path(game_id: int, kind: str, url: str) -> Path:
    return artwork_dir() / str(game_id) / f"{kind}{_extension_from_url(url)}"


def _path_exists(path: str | None) -> bool:
    return bool(path) and xbmcvfs.exists(path)


def _save_image(url: str, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(download_bytes(url))
    return str(dest)


def _needs_cover(game: dict) -> bool:
    if int(game.get("manual_metadata_locked") or 0):
        return False
    cover = game.get("cover_path")
    return not _path_exists(cover)


def enrich_game(
    db: GameDatabase,
    game_id: int,
    api_key: str | None = None,
    *,
    force: bool = False,
    verify_key: bool = True,
) -> ArtworkResult:
    api_key = api_key or _api_key()
    game = db.get_game(game_id)
    if not game:
        return ArtworkResult(game_id, "", "missing", "Game not found")
    if int(game.get("manual_metadata_locked") or 0):
        return ArtworkResult(game_id, game["title"], "locked", "Manual metadata lock enabled")
    if not force and not _needs_cover(game) and game.get("cover_path"):
        return ArtworkResult(game_id, game["title"], "cached", "Artwork already present")

    if not api_key:
        return ArtworkResult(game_id, game["title"], "no_api_key", "SteamGridDB API key is not set")
    if verify_key and not validate_api_key(api_key):
        return ArtworkResult(game_id, game["title"], "bad_api_key", "SteamGridDB API key is invalid")

    try:
        sgdb_game_id = game.get("sgdb_game_id")
        if not sgdb_game_id:
            match = search_game(game["title"], api_key)
            if not match:
                return ArtworkResult(game_id, game["title"], "no_match", f"No SteamGridDB match for '{game['title']}'")
            sgdb_game_id = int(match["id"])
        else:
            sgdb_game_id = int(sgdb_game_id)

        updates: dict = {
            "sgdb_game_id": sgdb_game_id,
            "metadata_updated_at": datetime.now().isoformat(timespec="seconds"),
        }

        grid = fetch_grid(sgdb_game_id, api_key)
        if not grid or not grid.get("url"):
            return ArtworkResult(
                game_id,
                game["title"],
                "no_art",
                f"No grid artwork on SteamGridDB for '{game['title']}'",
                sgdb_game_id=sgdb_game_id,
            )

        updates["cover_path"] = _save_image(grid["url"], _artwork_path(game_id, "poster", grid["url"]))

        if _fetch_fanart():
            hero = fetch_hero(sgdb_game_id, api_key)
            if hero and hero.get("url"):
                updates["fanart_path"] = _save_image(hero["url"], _artwork_path(game_id, "fanart", hero["url"]))

        if _fetch_logos():
            logo = fetch_logo(sgdb_game_id, api_key)
            if logo and logo.get("url"):
                updates["logo_path"] = _save_image(logo["url"], _artwork_path(game_id, "logo", logo["url"]))

        db.update_game_artwork(game_id, updates)
    except Exception as exc:
        return ArtworkResult(game_id, game["title"], "api_error", str(exc))
    if _debug():
        xbmc.log(
            f"[Ziro Games SGDB] enriched game_id={game_id} title={game['title']} sgdb_id={sgdb_game_id}",
            xbmc.LOGINFO,
        )
    return ArtworkResult(game_id, game["title"], "ok", "Artwork updated", sgdb_game_id=sgdb_game_id)


def enrich_missing_artwork(
    db: GameDatabase,
    progress: ProgressCallback | None = None,
    limit: int | None = None,
) -> ArtworkBatchResult:
    api_key = _api_key()
    if not api_key:
        batch = ArtworkBatchResult()
        batch.failed = 1
        batch.results.append(ArtworkResult(0, "", "no_api_key", "SteamGridDB API key is not set"))
        return batch
    if not validate_api_key(api_key):
        batch = ArtworkBatchResult()
        batch.failed = 1
        batch.results.append(ArtworkResult(0, "", "bad_api_key", "SteamGridDB API key is invalid"))
        return batch

    games = db.list_games_without_artwork(limit=limit)
    batch = ArtworkBatchResult()
    total = len(games)
    if not total:
        return batch

    for index, game in enumerate(games, start=1):
        if progress and not progress(int(index * 100 / total), game["title"]):
            break
        batch.processed += 1
        result = enrich_game(db, int(game["id"]), api_key=api_key, verify_key=False)
        batch.results.append(result)
        if result.status == "ok":
            batch.updated += 1
        elif result.status in {"cached", "locked"}:
            batch.skipped += 1
        else:
            batch.failed += 1
            message = result.message or result.status
            if result.status not in {"no_match", "no_art"}:
                xbmc.log(
                    f"[Ziro Games SGDB] failed game_id={game['id']} title={game['title']} status={result.status} msg={message}",
                    xbmc.LOGWARNING,
                )
            elif _debug():
                xbmc.log(
                    f"[Ziro Games SGDB] failed game_id={game['id']} title={game['title']} status={result.status} msg={result.message}",
                    xbmc.LOGINFO,
                )
        time.sleep(REQUEST_DELAY_SEC)

    return batch
