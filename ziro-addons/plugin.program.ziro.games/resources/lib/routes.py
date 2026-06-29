from __future__ import annotations

import xbmcaddon

from .db import GameDatabase
from .mock import MOCK_GAMES
from .platforms import get_platform, platform_ids
from .scanner import scan, source_for_platform

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")

GAME_SELECT = """
SELECT g.*, p.name AS platform,
       COALESCE(group_concat(ge.name, ', '), '') AS genres
FROM games g
LEFT JOIN platforms p ON p.id = g.platform_id
LEFT JOIN game_genres gg ON gg.game_id = g.id
LEFT JOIN genres ge ON ge.id = gg.genre_id
WHERE g.hidden=0
"""
GROUP_ORDER = " GROUP BY g.id "


class Router:
    def __init__(self, db: GameDatabase) -> None:
        self.db = db

    def _with_mock(self, rows: list[dict]) -> list[dict]:
        if rows:
            return rows
        if ADDON.getSettingBool("dev_mock_library"):
            return MOCK_GAMES
        return []

    def continue_playing(self) -> list[dict]:
        rows = self.db.rows(GAME_SELECT + " AND g.last_played IS NOT NULL" + GROUP_ORDER + " ORDER BY g.last_played DESC LIMIT 25")
        return self._with_mock([g for g in MOCK_GAMES if g.get("last_played")] if not rows and ADDON.getSettingBool("dev_mock_library") else rows)

    def recently_added(self) -> list[dict]:
        rows = self.db.rows(GAME_SELECT + GROUP_ORDER + " ORDER BY g.date_added DESC LIMIT 50")
        return self._with_mock(rows)

    def favorites(self) -> list[dict]:
        rows = self.db.rows(GAME_SELECT + " AND g.favorite=1" + GROUP_ORDER + " ORDER BY g.sort_title ASC LIMIT 50")
        return self._with_mock([g for g in MOCK_GAMES if g.get("favorite")] if not rows and ADDON.getSettingBool("dev_mock_library") else rows)

    def platforms(self) -> list[dict]:
        return self.db.rows("SELECT * FROM platforms ORDER BY sort_order, name")

    def by_platform(self, platform_id: str) -> list[dict]:
        rows = self.db.rows(GAME_SELECT + " AND g.platform_id=?" + GROUP_ORDER + " ORDER BY g.sort_title", (platform_id,))
        if not rows and ADDON.getSettingBool("dev_mock_library"):
            return [g for g in MOCK_GAMES if g["platform_id"] == platform_id]
        return rows

    def genres(self) -> list[dict]:
        return self.db.rows("SELECT * FROM genres ORDER BY name")

    def by_genre(self, genre_id: str) -> list[dict]:
        rows = self.db.rows(
            GAME_SELECT + " AND EXISTS (SELECT 1 FROM game_genres gg2 WHERE gg2.game_id=g.id AND gg2.genre_id=?)" + GROUP_ORDER + " ORDER BY g.sort_title",
            (genre_id,),
        )
        if not rows and ADDON.getSettingBool("dev_mock_library"):
            return [g for g in MOCK_GAMES if genre_id.lower() in g.get("genres", "").lower()]
        return rows

    def sources(self) -> list[dict]:
        return self.db.list_sources(enabled_only=False)

    def add_source(self, platform_id: str, folder_path: str) -> int | None:
        if platform_id not in platform_ids():
            raise ValueError(f"Unsupported platform: {platform_id}")
        return self.db.ensure_source(source_for_platform(platform_id, folder_path))

    def remove_source(self, source_id: int) -> None:
        self.db.delete_source(source_id)

    def toggle_favorite(self, game_id: int) -> None:
        if game_id < 0:
            return
        self.db.execute("UPDATE games SET favorite = CASE favorite WHEN 1 THEN 0 ELSE 1 END WHERE id=?", (game_id,))

    def scan_sources(self) -> int:
        return scan(self.db)
