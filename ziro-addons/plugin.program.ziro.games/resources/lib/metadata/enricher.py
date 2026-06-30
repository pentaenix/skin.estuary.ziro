from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import xbmc
import xbmcaddon
import xbmcgui

from ..db import GameDatabase
from ..paths import artwork_dir
from .http_client import download_bytes
from .providers import (
    PROVIDER_SCREENSCRAPER,
    PROVIDER_SKRAPER,
    PROVIDER_STEAMGRIDDB,
    artwork_show_picker,
    game_artwork_provider,
    steamgriddb_api_key,
)
from .screenscraper import (
    credentials_configured,
    extract_art_urls,
    extract_metadata,
    lookup_game,
    search_games,
    validate_credentials,
)
from .genre_sync import map_genre_names_to_ids
from .local_metadata import import_metadata_for_game
from .sgdb_enricher import enrich_game_sgdb
from .sgdb_log import log_warning
from .ss_log import log_warning as ss_log_warning
from .steamgriddb import search_autocomplete_all, validate_api_key

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")
REQUEST_DELAY_SEC = 0.55


@dataclass
class ArtworkResult:
    game_id: int
    title: str
    status: str
    message: str = ""
    ss_game_id: int | None = None
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
        failures = [result for result in self.results if result.status not in {"ok", "cached", "locked"}]
        if failures:
            lines.append("")
            lines.append("Failed titles:")
            for result in failures[:20]:
                title = result.title or f"Game #{result.game_id}"
                detail = result.message or result.status
                lines.append(f"• {title}: {detail}")
            if len(failures) > 20:
                lines.append(f"…and {len(failures) - 20} more (see ss.log / sgdb.log)")
        return "\n".join(lines)


ProgressCallback = Callable[[int, str], bool]


def _path_exists(path: str | None) -> bool:
    import xbmcvfs

    return bool(path) and xbmcvfs.exists(path)


def _needs_cover(game: dict) -> bool:
    if int(game.get("manual_metadata_locked") or 0):
        return False
    return not _path_exists(game.get("cover_path"))


def _extension_from_url(url: str, fallback: str = ".png") -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return suffix
    return fallback


def _artwork_path(game_id: int, kind: str, url: str, *, fallback: str = ".png") -> Path:
    return artwork_dir() / str(game_id) / f"{kind}{_extension_from_url(url, fallback)}"


def _save_image(url: str, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(download_bytes(url))
    return str(dest)


def _ss_game_label(jeu: dict) -> str:
    meta = extract_metadata(jeu)
    title = meta.get("title") or f"Game #{meta.get('ss_game_id') or jeu.get('id')}"
    year = meta.get("release_year")
    if year:
        return f"{title} ({year})"
    return title


def _pick_sgdb_match(game: dict, *, force_picker: bool = False) -> dict | None:
    api_key = steamgriddb_api_key()
    if not api_key:
        return None
    results = search_autocomplete_all(game["title"], api_key, limit=30)
    if not results:
        return None
    if not force_picker and not artwork_show_picker() and len(results) == 1:
        return results[0]
    if not force_picker and not artwork_show_picker():
        from .steamgriddb import search_game

        return search_game(game["title"], api_key)
    labels = [str(item.get("name") or item.get("title") or f"#{item.get('id')}") for item in results]
    index = xbmcgui.Dialog().select(f"SteamGridDB — {game['title']}", labels)
    if index < 0:
        return None
    return results[index]


def _pick_ss_game(game: dict, *, force_picker: bool = False) -> dict | None:
    results = search_games(game["platform_id"], game["title"], limit=30)
    if not results:
        return None
    if not force_picker and not artwork_show_picker() and len(results) == 1:
        return results[0]
    if not force_picker and not artwork_show_picker():
        return lookup_game(
            platform_id=game["platform_id"],
            title=game["title"],
            rom_path=game.get("rom_path") or "",
            ss_game_id=int(game["ss_game_id"]) if game.get("ss_game_id") else None,
        )
    labels = [_ss_game_label(item) for item in results]
    index = xbmcgui.Dialog().select(f"ScreenScraper — {game['title']}", labels)
    if index < 0:
        return None
    return results[index]


def _apply_metadata(db: GameDatabase, game_id: int, meta: dict) -> None:
    updates: dict = {}
    if meta.get("description"):
        updates["description"] = meta["description"]
    if meta.get("developer"):
        updates["developer"] = meta["developer"]
    if meta.get("publisher"):
        updates["publisher"] = meta["publisher"]
    if meta.get("release_year"):
        updates["release_year"] = int(meta["release_year"])
    if updates:
        db.update_game_artwork(game_id, updates)
    genre_names = meta.get("genre_names") or []
    if isinstance(genre_names, str):
        genre_names = [part.strip() for part in genre_names.split(",") if part.strip()]
    genre_ids = map_genre_names_to_ids(genre_names)
    if genre_ids:
        db.set_game_genres(game_id, genre_ids)


def _enrich_screenscraper(
    db: GameDatabase,
    game_id: int,
    game: dict,
    *,
    force_picker: bool = False,
) -> ArtworkResult:
    if not credentials_configured():
        return ArtworkResult(
            game_id,
            game["title"],
            "no_credentials",
            "Set ScreenScraper username, password, developer ID, and developer password in Ziro Games settings",
        )
    if not validate_credentials():
        return ArtworkResult(game_id, game["title"], "bad_credentials", "ScreenScraper credentials are invalid")

    try:
        jeu = _pick_ss_game(game, force_picker=force_picker)
        if not jeu and game.get("ss_game_id"):
            jeu = lookup_game(
                platform_id=game["platform_id"],
                title=game["title"],
                rom_path=game.get("rom_path") or "",
                ss_game_id=int(game["ss_game_id"]),
            )
        if not jeu:
            return ArtworkResult(game_id, game["title"], "no_match", f"No ScreenScraper match for '{game['title']}'")

        meta = extract_metadata(jeu)
        art = extract_art_urls(jeu)
        if not art.get("cover"):
            return ArtworkResult(
                game_id,
                game["title"],
                "no_art",
                f"No box art on ScreenScraper for '{game['title']}'",
                ss_game_id=meta.get("ss_game_id"),
            )

        updates: dict = {
            "ss_game_id": meta.get("ss_game_id"),
            "metadata_updated_at": datetime.now().isoformat(timespec="seconds"),
            "cover_path": _save_image(art["cover"], _artwork_path(game_id, "cover", art["cover"])),
        }
        _apply_metadata(db, game_id, meta)
        if ADDON.getSettingBool("metadata_fetch_fanart") and art.get("fanart"):
            updates["fanart_path"] = _save_image(art["fanart"], _artwork_path(game_id, "fanart", art["fanart"]))
        if ADDON.getSettingBool("metadata_fetch_logos") and art.get("logo"):
            updates["logo_path"] = _save_image(art["logo"], _artwork_path(game_id, "logo", art["logo"]))
        if ADDON.getSettingBool("metadata_fetch_screenshots") and art.get("screenshot"):
            updates["screenshot_path"] = _save_image(
                art["screenshot"],
                _artwork_path(game_id, "screenshot", art["screenshot"]),
            )
        if ADDON.getSettingBool("metadata_fetch_videos") and art.get("video"):
            updates["video_path"] = _save_image(
                art["video"],
                _artwork_path(game_id, "video", art["video"], fallback=".mp4"),
            )
        db.update_game_artwork(game_id, updates)
        return ArtworkResult(
            game_id,
            game["title"],
            "ok",
            "Artwork updated",
            ss_game_id=updates.get("ss_game_id"),
        )
    except Exception as exc:
        return ArtworkResult(game_id, game["title"], "api_error", f"{game['title']}: {exc}")


def _enrich_steamgriddb(
    db: GameDatabase,
    game_id: int,
    game: dict,
    *,
    force_picker: bool = False,
) -> ArtworkResult:
    if not steamgriddb_api_key():
        return ArtworkResult(game_id, game["title"], "no_credentials", "SteamGridDB API key is not set")
    if not validate_api_key(steamgriddb_api_key()):
        return ArtworkResult(game_id, game["title"], "bad_credentials", "SteamGridDB API key is invalid")
    try:
        match = _pick_sgdb_match(game, force_picker=force_picker)
        updates, sgdb_id = enrich_game_sgdb(db, game_id, game, sgdb_match=match, verify_key=False)
        return ArtworkResult(game_id, game["title"], "ok", "Artwork updated", sgdb_game_id=sgdb_id)
    except Exception as exc:
        return ArtworkResult(game_id, game["title"], "api_error", f"{game['title']}: {exc}")


def _enrich_skraper(
    db: GameDatabase,
    game_id: int,
    game: dict,
    *,
    force: bool = False,
) -> ArtworkResult:
    status, message = import_metadata_for_game(db, game_id, force=force)
    if status == "ok":
        return ArtworkResult(game_id, game["title"], "ok", message)
    if status == "locked":
        return ArtworkResult(game_id, game["title"], "locked", message)
    if status == "no_match":
        return ArtworkResult(game_id, game["title"], "no_match", message)
    return ArtworkResult(game_id, game["title"], status, message)


def enrich_game(
    db: GameDatabase,
    game_id: int,
    *,
    force: bool = False,
    verify_key: bool = True,
    force_picker: bool = False,
) -> ArtworkResult:
    game = db.get_game(game_id)
    if not game:
        return ArtworkResult(game_id, "", "missing", "Game not found")
    if int(game.get("manual_metadata_locked") or 0):
        return ArtworkResult(game_id, game["title"], "locked", "Manual metadata lock enabled")
    if not force and not _needs_cover(game) and game.get("cover_path"):
        return ArtworkResult(game_id, game["title"], "cached", "Artwork already present")

    provider = game_artwork_provider()
    if provider == PROVIDER_STEAMGRIDDB:
        return _enrich_steamgriddb(db, game_id, game, force_picker=force_picker or force)
    if provider == PROVIDER_SKRAPER:
        return _enrich_skraper(db, game_id, game, force=force)
    return _enrich_screenscraper(db, game_id, game, force_picker=force_picker or force)


def enrich_missing_artwork(
    db: GameDatabase,
    progress: ProgressCallback | None = None,
    limit: int | None = None,
) -> ArtworkBatchResult:
    batch = ArtworkBatchResult()
    provider = game_artwork_provider()
    games = db.list_games_without_artwork(limit=limit)

    if provider == PROVIDER_SKRAPER:
        total = len(games)
        for index, game in enumerate(games, start=1):
            if progress and not progress(int(index * 100 / max(total, 1)), game["title"]):
                break
            batch.processed += 1
            result = enrich_game(db, int(game["id"]), verify_key=False)
            batch.results.append(result)
            if result.status == "ok":
                batch.updated += 1
            elif result.status in {"cached", "locked"}:
                batch.skipped += 1
            else:
                batch.failed += 1
        return batch

    if provider == PROVIDER_STEAMGRIDDB:
        if not steamgriddb_api_key():
            batch.failed = 1
            batch.results.append(ArtworkResult(0, "", "no_credentials", "SteamGridDB API key is not set"))
            return batch
        if not validate_api_key(steamgriddb_api_key()):
            batch.failed = 1
            batch.results.append(ArtworkResult(0, "", "bad_credentials", "SteamGridDB API key is invalid"))
            return batch
    elif not credentials_configured():
        batch.failed = 1
        batch.results.append(
            ArtworkResult(
                0,
                "",
                "no_credentials",
                "Set ScreenScraper username, password, developer ID, and developer password",
            )
        )
        return batch
    elif not validate_credentials():
        batch.failed = 1
        batch.results.append(ArtworkResult(0, "", "bad_credentials", "ScreenScraper credentials are invalid"))
        return batch

    total = len(games)
    if not total:
        return batch

    log_fn = log_warning if provider == PROVIDER_STEAMGRIDDB else ss_log_warning
    for index, game in enumerate(games, start=1):
        if progress and not progress(int(index * 100 / total), game["title"]):
            break
        batch.processed += 1
        result = enrich_game(db, int(game["id"]), verify_key=False)
        batch.results.append(result)
        if result.status == "ok":
            batch.updated += 1
        elif result.status in {"cached", "locked"}:
            batch.skipped += 1
        else:
            batch.failed += 1
            log_fn(f"failed title={result.title} status={result.status} msg={result.message or result.status}")
        time.sleep(REQUEST_DELAY_SEC)

    return batch


def enrich_all_artwork(
    db: GameDatabase,
    progress: ProgressCallback | None = None,
    limit: int | None = None,
) -> ArtworkBatchResult:
    batch = ArtworkBatchResult()
    provider = game_artwork_provider()
    games = db.list_games_for_artwork_refresh(limit=limit)

    if provider == PROVIDER_SKRAPER:
        total = len(games)
        for index, game in enumerate(games, start=1):
            if progress and not progress(int(index * 100 / max(total, 1)), game["title"]):
                break
            batch.processed += 1
            result = enrich_game(db, int(game["id"]), force=True, verify_key=False)
            batch.results.append(result)
            if result.status == "ok":
                batch.updated += 1
            elif result.status in {"cached", "locked"}:
                batch.skipped += 1
            else:
                batch.failed += 1
        try:
            from ..home_state import refresh_home_properties

            refresh_home_properties(db)
        except Exception:
            pass
        return batch

    if provider == PROVIDER_STEAMGRIDDB:
        if not steamgriddb_api_key():
            batch.failed = 1
            batch.results.append(ArtworkResult(0, "", "no_credentials", "SteamGridDB API key is not set"))
            return batch
        if not validate_api_key(steamgriddb_api_key()):
            batch.failed = 1
            batch.results.append(ArtworkResult(0, "", "bad_credentials", "SteamGridDB API key is invalid"))
            return batch
    elif not credentials_configured():
        batch.failed = 1
        batch.results.append(
            ArtworkResult(
                0,
                "",
                "no_credentials",
                "Set ScreenScraper username, password, developer ID, and developer password",
            )
        )
        return batch
    elif not validate_credentials():
        batch.failed = 1
        batch.results.append(ArtworkResult(0, "", "bad_credentials", "ScreenScraper credentials are invalid"))
        return batch

    total = len(games)
    if not total:
        return batch

    log_fn = log_warning if provider == PROVIDER_STEAMGRIDDB else ss_log_warning
    for index, game in enumerate(games, start=1):
        if progress and not progress(int(index * 100 / total), game["title"]):
            break
        batch.processed += 1
        result = enrich_game(db, int(game["id"]), force=True, verify_key=False)
        batch.results.append(result)
        if result.status == "ok":
            batch.updated += 1
        elif result.status in {"cached", "locked"}:
            batch.skipped += 1
        else:
            batch.failed += 1
            log_fn(f"failed title={result.title} status={result.status} msg={result.message or result.status}")
        time.sleep(REQUEST_DELAY_SEC)

    try:
        from ..home_state import refresh_home_properties

        refresh_home_properties(db)
    except Exception:
        pass

    return batch
