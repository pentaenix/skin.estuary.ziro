from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import xbmc
import xbmcaddon

from ..db import GameDatabase
from ..paths import artwork_dir
from .http_client import download_bytes
from .screenscraper import (
    credentials_configured,
    extract_art_urls,
    extract_metadata,
    lookup_game,
    validate_credentials,
)
from .ss_log import log_warning

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")
REQUEST_DELAY_SEC = 0.55


@dataclass
class ArtworkResult:
    game_id: int
    title: str
    status: str
    message: str = ""
    ss_game_id: int | None = None


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
                lines.append(f"…and {len(failures) - 20} more (see ss.log)")
            if any(result.status == "api_error" for result in failures):
                lines.append("")
                lines.append("Full API URLs and bodies: addon_data/plugin.program.ziro.games/ss.log")
        return "\n".join(lines)


ProgressCallback = Callable[[int, str], bool]


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
    import xbmcvfs

    return bool(path) and xbmcvfs.exists(path)


def _save_image(url: str, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(download_bytes(url))
    return str(dest)


def _needs_cover(game: dict) -> bool:
    if int(game.get("manual_metadata_locked") or 0):
        return False
    return not _path_exists(game.get("cover_path"))


def enrich_game(
    db: GameDatabase,
    game_id: int,
    *,
    force: bool = False,
    verify_key: bool = True,
) -> ArtworkResult:
    game = db.get_game(game_id)
    if not game:
        return ArtworkResult(game_id, "", "missing", "Game not found")
    if int(game.get("manual_metadata_locked") or 0):
        return ArtworkResult(game_id, game["title"], "locked", "Manual metadata lock enabled")
    if not force and not _needs_cover(game) and game.get("cover_path"):
        return ArtworkResult(game_id, game["title"], "cached", "Artwork already present")

    if not credentials_configured():
        return ArtworkResult(
            game_id,
            game["title"],
            "no_credentials",
            "Set ScreenScraper username, password, developer ID, and developer password in Ziro Games settings",
        )
    if verify_key and not validate_credentials():
        return ArtworkResult(
            game_id,
            game["title"],
            "bad_credentials",
            "ScreenScraper credentials are invalid or incomplete",
        )

    try:
        jeu = lookup_game(
            platform_id=game["platform_id"],
            title=game["title"],
            rom_path=game.get("rom_path") or "",
            ss_game_id=int(game["ss_game_id"]) if game.get("ss_game_id") else None,
        )
        if not jeu:
            return ArtworkResult(
                game_id,
                game["title"],
                "no_match",
                f"No ScreenScraper match for '{game['title']}'",
            )

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
        if meta.get("description"):
            updates["description"] = meta["description"]

        if _fetch_fanart() and art.get("fanart"):
            updates["fanart_path"] = _save_image(art["fanart"], _artwork_path(game_id, "fanart", art["fanart"]))

        if _fetch_logos() and art.get("logo"):
            updates["logo_path"] = _save_image(art["logo"], _artwork_path(game_id, "logo", art["logo"]))

        if art.get("screenshot"):
            updates["screenshot_path"] = _save_image(
                art["screenshot"],
                _artwork_path(game_id, "screenshot", art["screenshot"]),
            )

        db.update_game_artwork(game_id, updates)
    except Exception as exc:
        return ArtworkResult(game_id, game["title"], "api_error", f"{game['title']}: {exc}")

    if _debug():
        xbmc.log(
            f"[Ziro Games SS] enriched game_id={game_id} title={game['title']} ss_id={updates.get('ss_game_id')}",
            xbmc.LOGINFO,
        )
    return ArtworkResult(
        game_id,
        game["title"],
        "ok",
        "Artwork updated",
        ss_game_id=updates.get("ss_game_id"),
    )


def enrich_missing_artwork(
    db: GameDatabase,
    progress: ProgressCallback | None = None,
    limit: int | None = None,
) -> ArtworkBatchResult:
    batch = ArtworkBatchResult()
    if not credentials_configured():
        batch.failed = 1
        batch.results.append(
            ArtworkResult(0, "", "no_credentials", "Set ScreenScraper username, password, developer ID, and developer password in Ziro Games settings")
        )
        return batch
    if not validate_credentials():
        batch.failed = 1
        batch.results.append(
            ArtworkResult(0, "", "bad_credentials", "ScreenScraper credentials are invalid or incomplete")
        )
        return batch

    games = db.list_games_without_artwork(limit=limit)
    total = len(games)
    if not total:
        return batch

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
            message = result.message or result.status
            title = result.title or game.get("title") or f"Game #{game.get('id')}"
            log_warning(f"failed title={title} status={result.status} msg={message}")
        time.sleep(REQUEST_DELAY_SEC)

    return batch
