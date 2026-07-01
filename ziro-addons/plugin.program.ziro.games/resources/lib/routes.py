from __future__ import annotations

from .db import GameDatabase
from .metadata import ArtworkBatchResult, enrich_all_artwork, enrich_game, enrich_missing_artwork
from .paths_filter import is_library_rom_path, is_valid_game_title, rom_file_exists
from .platforms import get_platform, platform_ids
from .scanner import ScanResult, scan, source_for_platform

GAME_SELECT = """
SELECT g.*, p.name AS platform,
       COALESCE(group_concat(ge.name, ', '), '') AS genres,
       s.folder_path AS source_folder
FROM games g
LEFT JOIN platforms p ON p.id = g.platform_id
LEFT JOIN sources s ON s.id = g.source_id
LEFT JOIN game_genres gg ON gg.game_id = g.id
LEFT JOIN genres ge ON ge.id = gg.genre_id
WHERE g.hidden=0
  AND LENGTH(TRIM(g.title)) > 0
  AND g.rom_path NOT LIKE 'mock://%'
  AND g.rom_path NOT LIKE 'test://%'
  AND g.rom_path NOT LIKE '%ziro-addons%'
  AND g.rom_path NOT LIKE '%skin.estuary.ziro%'
  AND g.rom_path NOT LIKE '%plugin.program.ziro.games%'
  AND g.rom_path NOT LIKE '%/dist/%'
  AND g.rom_path NOT LIKE '%\\dist\\%'
  AND g.title NOT LIKE '%.zip'
  AND g.title NOT LIKE '%plugin.program%'
  AND g.title NOT LIKE '%script.ziro%'
"""
GROUP_ORDER = " GROUP BY g.id "


class Router:
    def __init__(self, db: GameDatabase) -> None:
        self.db = db

    def _filter_rows(self, rows: list[dict]) -> list[dict]:
        filtered: list[dict] = []
        for row in rows:
            rom_path = row.get("rom_path", "")
            if not is_library_rom_path(rom_path):
                continue
            if not rom_file_exists(rom_path):
                continue
            if not (row.get("title") or "").strip():
                continue
            if not is_valid_game_title(row.get("title", "")):
                continue
            filtered.append(row)
        return filtered

    def continue_playing(self) -> list[dict]:
        rows = self.db.rows(
            GAME_SELECT
            + " AND g.play_count > 0 AND g.last_played IS NOT NULL"
            + GROUP_ORDER
            + " ORDER BY g.last_played DESC LIMIT 25"
        )
        return self._filter_rows(rows)

    def recently_added(self, limit: int = 50) -> list[dict]:
        rows = self.db.rows(GAME_SELECT + GROUP_ORDER + " ORDER BY g.date_added DESC LIMIT ?", (limit,))
        return self._filter_rows(rows)

    def all_games(self, limit: int = 5000) -> list[dict]:
        rows = self.db.rows(GAME_SELECT + GROUP_ORDER + " ORDER BY g.sort_title ASC LIMIT ?", (limit,))
        return self._filter_rows(rows)

    def favorites(self) -> list[dict]:
        rows = self.db.rows(
            GAME_SELECT + " AND g.favorite=1" + GROUP_ORDER + " ORDER BY g.sort_title ASC LIMIT 50"
        )
        return self._filter_rows(rows)

    def platforms(self) -> list[dict]:
        return self.db.rows(
            """
            SELECT p.*, COUNT(g.id) AS game_count
            FROM platforms p
            INNER JOIN games g ON g.platform_id = p.id AND g.hidden = 0
              AND LENGTH(TRIM(g.title)) > 0
              AND g.rom_path NOT LIKE 'mock://%'
              AND g.rom_path NOT LIKE 'test://%'
              AND g.rom_path NOT LIKE '%ziro-addons%'
              AND g.rom_path NOT LIKE '%skin.estuary.ziro%'
              AND g.rom_path NOT LIKE '%plugin.program.ziro.games%'
              AND g.rom_path NOT LIKE '%/dist/%'
              AND g.rom_path NOT LIKE '%\\dist\\%'
              AND g.title NOT LIKE '%.zip'
              AND g.title NOT LIKE '%plugin.program%'
            GROUP BY p.id
            HAVING COUNT(g.id) > 0
            ORDER BY p.sort_order, p.name
            """
        )

    def by_platform(self, platform_id: str) -> list[dict]:
        rows = self.db.rows(
            GAME_SELECT + " AND g.platform_id=?" + GROUP_ORDER + " ORDER BY g.sort_title",
            (platform_id,),
        )
        return self._filter_rows(rows)

    def genres(self) -> list[dict]:
        return self.db.rows(
            """
            SELECT g.*, COUNT(DISTINCT gg.game_id) AS game_count
            FROM genres g
            INNER JOIN game_genres gg ON gg.genre_id = g.id
            INNER JOIN games games ON games.id = gg.game_id AND games.hidden = 0
            GROUP BY g.id
            HAVING game_count > 0
            ORDER BY g.name
            """
        )

    def by_genre(self, genre_id: str) -> list[dict]:
        rows = self.db.rows(
            GAME_SELECT
            + " AND EXISTS (SELECT 1 FROM game_genres gg2 WHERE gg2.game_id=g.id AND gg2.genre_id=?)"
            + GROUP_ORDER
            + " ORDER BY g.sort_title",
            (genre_id,),
        )
        return self._filter_rows(rows)

    def sources(self) -> list[dict]:
        return self.db.list_sources(enabled_only=False)

    def add_source(self, platform_id: str, folder_path: str) -> int | None:
        if platform_id not in platform_ids():
            raise ValueError(f"Unsupported platform: {platform_id}")
        return self.db.ensure_source(source_for_platform(platform_id, folder_path))

    def remove_source(self, source_id: int, *, purge_games: bool = False) -> None:
        self.db.delete_source(source_id, purge_games=purge_games)

    def toggle_favorite(self, game_id: int) -> None:
        self.db.execute(
            "UPDATE games SET favorite = CASE favorite WHEN 1 THEN 0 ELSE 1 END WHERE id=?",
            (game_id,),
        )

    def scan_sources(self) -> ScanResult:
        return scan(self.db)

    def refresh_artwork(self, game_id: int):
        return enrich_game(self.db, game_id, force=True, force_picker=True)

    def fetch_missing_artwork(self, progress=None, limit: int | None = None) -> ArtworkBatchResult:
        return enrich_missing_artwork(self.db, progress=progress, limit=limit)

    def refresh_all_artwork(self, progress=None, limit: int | None = None) -> ArtworkBatchResult:
        return enrich_all_artwork(self.db, progress=progress, limit=limit)
