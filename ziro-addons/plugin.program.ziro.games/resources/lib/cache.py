from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import xbmc
import xbmcgui
import xbmcvfs

from .db import GameDatabase
from .metadata.local_metadata import clear_gamelist_cache
from .metadata.platform_art import _map_path, platform_art_dir
from .paths import ADDON_ID, artwork_dir

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
        if not self.games_updated and not self.files_removed:
            return "No downloaded artwork cache was found to clear."
        return (
            f"Removed {self.files_removed} cached files.\n"
            f"Cleared artwork on {self.games_updated} games."
        )


def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def is_downloaded_art_path(path: str | None) -> bool:
    if not path or not str(path).strip():
        return False
    norm = _norm(str(path))
    if ADDON_ID.lower() not in norm:
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
    if not path:
        return 0
    removed = 0
    for candidate in {path, xbmcvfs.translatePath(path)}:
        if not candidate or not xbmcvfs.exists(candidate):
            continue
        try:
            xbmcvfs.delete(candidate)
            removed += 1
        except Exception:
            try:
                Path(candidate).unlink(missing_ok=True)
                removed += 1
            except Exception as exc:
                xbmc.log(f"[Games] cache delete failed file={candidate}: {exc}", xbmc.LOGWARNING)
    return removed


def _field_matches_cache_sql(field: str) -> str:
    return (
        f"({field} LIKE '%{ADDON_ID}/artwork/%' OR {field} LIKE '%{ADDON_ID}\\artwork\\%'"
        f" OR {field} LIKE '%{ADDON_ID}/platform_art/%' OR {field} LIKE '%{ADDON_ID}\\platform_art\\%')"
    )


def _count_games_with_cache_paths(db: GameDatabase) -> int:
    row = db.one(
        f"""
        SELECT COUNT(DISTINCT id) AS n FROM games
        WHERE {" OR ".join(_field_matches_cache_sql(field) for field in ART_PATH_FIELDS)}
        """
    )
    return int(row["n"]) if row else 0


def _clear_artwork_columns_sql(db: GameDatabase) -> None:
    for field in ART_PATH_FIELDS:
        db.execute(f"UPDATE games SET {field}='' WHERE {_field_matches_cache_sql(field)}")
    db.execute(
        f"""
        UPDATE games
        SET sgdb_game_id=NULL, ss_game_id=NULL, manual_metadata_locked=0
        WHERE {" OR ".join(_field_matches_cache_sql(field) for field in ART_PATH_FIELDS)}
        """
    )


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

    updated_ids: set[int] = set()
    for row in rows:
        game_id = int(row["id"])
        updates: dict[str, str] = {}
        for field in ART_PATH_FIELDS:
            value = row.get(field) or ""
            if is_downloaded_art_path(value):
                updates[field] = ""
                result.files_removed += _remove_path_file(value)
        if not updates:
            continue
        db.update_game_artwork(game_id, updates)
        db.execute(
            """
            UPDATE games
            SET sgdb_game_id=NULL, ss_game_id=NULL, manual_metadata_locked=0
            WHERE id=?
            """,
            (game_id,),
        )
        updated_ids.add(game_id)

    if game_ids:
        result.games_updated = len(updated_ids)
    else:
        before = _count_games_with_cache_paths(db)
        _clear_artwork_columns_sql(db)
        after = _count_games_with_cache_paths(db)
        result.games_updated = max(len(updated_ids), before - after, before)

    xbmc.log(
        f"[Games] clear cache files={result.files_removed} games={result.games_updated}",
        xbmc.LOGINFO,
    )
    clear_gamelist_cache()
    return result


def clear_artwork_for_source(db: GameDatabase, source_id: int) -> ClearCacheResult:
    rows = db.rows("SELECT id FROM games WHERE source_id=?", (source_id,))
    game_ids = [int(row["id"]) for row in rows]
    if not game_ids:
        return ClearCacheResult()
    return clear_downloaded_artwork(db, game_ids=game_ids, include_hidden=True)


def refresh_games_ui(db: GameDatabase | None = None) -> None:
    from .home_state import refresh_home_properties

    refresh_home_properties(db)
    for list_id in (17290, 17300, 17310, 17320):
        try:
            xbmc.executebuiltin(f"Container.Update({list_id},replace)")
        except Exception:
            pass
    xbmc.executebuiltin("Container.Refresh")
    xbmc.sleep(250)
    xbmc.executebuiltin("Container.Refresh")
