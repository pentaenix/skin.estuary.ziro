from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import xbmc
import xbmcvfs

from .db import GameDatabase
from .metadata.local_metadata import clear_gamelist_cache
from .metadata.platform_art import _map_path, platform_art_dir
from .paths import artwork_dir, userdata_dir

ART_PATH_FIELDS = (
    "cover_path",
    "fanart_path",
    "logo_path",
    "screenshot_path",
    "video_path",
)


@dataclass
class ClearCacheResult:
    files_removed: int = 0
    games_updated: int = 0

    def summary(self) -> str:
        return (
            f"Removed {self.files_removed} cached files.\n"
            f"Cleared artwork on {self.games_updated} games."
        )


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def _userdata_prefix() -> str:
    return _norm(str(userdata_dir()))


def is_downloaded_art_path(path: str | None) -> bool:
    if not path or not str(path).strip():
        return False
    norm = _norm(str(path))
    prefix = _userdata_prefix()
    if prefix not in norm:
        return False
    return "/artwork/" in norm or "/platform_art/" in norm


def _delete_folder_contents(folder: Path) -> int:
    removed = 0
    if not folder.exists():
        return removed
    for child in folder.iterdir():
        try:
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
                removed += 1
            elif child.is_dir():
                count = sum(1 for f in child.rglob("*") if f.is_file())
                shutil.rmtree(child, ignore_errors=True)
                removed += count
        except Exception as exc:
            xbmc.log(f"[Games] cache delete failed path={child}: {exc}", xbmc.LOGWARNING)
    return removed


def _remove_path_file(path: str) -> int:
    if not path or not xbmcvfs.exists(path):
        return 0
    try:
        xbmcvfs.delete(path)
        return 1
    except Exception:
        try:
            Path(path).unlink(missing_ok=True)
            return 1
        except Exception as exc:
            xbmc.log(f"[Games] cache delete failed file={path}: {exc}", xbmc.LOGWARNING)
    return 0


def clear_downloaded_artwork(
    db: GameDatabase,
    *,
    game_ids: list[int] | None = None,
    include_hidden: bool = True,
) -> ClearCacheResult:
    result = ClearCacheResult()
    result.files_removed += _delete_folder_contents(artwork_dir())
    result.files_removed += _delete_folder_contents(platform_art_dir())
    map_path = _map_path()
    if map_path.exists():
        try:
            map_path.unlink()
            result.files_removed += 1
        except Exception as exc:
            xbmc.log(f"[Games] cache delete failed map={map_path}: {exc}", xbmc.LOGWARNING)

    where = "WHERE 1=1"
    args: tuple = ()
    if game_ids:
        placeholders = ",".join("?" for _ in game_ids)
        where += f" AND id IN ({placeholders})"
        args = tuple(game_ids)
    elif not include_hidden:
        where += " AND hidden=0"

    rows = db.rows(
        f"""
        SELECT id, cover_path, fanart_path, logo_path, screenshot_path, video_path
        FROM games
        {where}
        """,
        args,
    )

    for row in rows:
        updates: dict[str, str] = {}
        for field in ART_PATH_FIELDS:
            value = row.get(field) or ""
            if is_downloaded_art_path(value):
                updates[field] = ""
                result.files_removed += _remove_path_file(value)
        if not updates:
            continue
        db.update_game_artwork(int(row["id"]), updates)
        db.execute(
            """
            UPDATE games
            SET sgdb_game_id=NULL, ss_game_id=NULL, manual_metadata_locked=0
            WHERE id=?
            """,
            (row["id"],),
        )
        result.games_updated += 1

    clear_gamelist_cache()
    return result


def clear_artwork_for_source(db: GameDatabase, source_id: int) -> ClearCacheResult:
    rows = db.rows("SELECT id FROM games WHERE source_id=?", (source_id,))
    game_ids = [int(row["id"]) for row in rows]
    if not game_ids:
        return ClearCacheResult()
    return clear_downloaded_artwork(db, game_ids=game_ids, include_hidden=True)
