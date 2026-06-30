from __future__ import annotations

import xbmc
import xbmcgui

from .db import GameDatabase
from .platforms import platform_ids

HOME_WINDOW_ID = 10000
PROPERTY_PREFIX = "ZiroGames.Platform."

_VALID_GAMES_WHERE = """
    hidden = 0
    AND LENGTH(TRIM(title)) > 0
    AND rom_path NOT LIKE '%ziro-addons%'
    AND rom_path NOT LIKE '%skin.estuary.ziro%'
    AND rom_path NOT LIKE '%plugin.program.ziro.games%'
    AND rom_path NOT LIKE '%/dist/%'
    AND rom_path NOT LIKE '%\\dist\\%'
    AND title NOT LIKE '%.zip'
    AND title NOT LIKE '%plugin.program%'
    AND title NOT LIKE '%script.ziro%'
"""


def refresh_home_platform_properties(db: GameDatabase | None = None) -> None:
    db = db or GameDatabase()
    window = xbmcgui.Window(HOME_WINDOW_ID)
    for platform_id in platform_ids():
        window.clearProperty(f"{PROPERTY_PREFIX}{platform_id}")
    rows = db.rows(
        f"""
        SELECT platform_id, COUNT(*) AS game_count
        FROM games
        WHERE {_VALID_GAMES_WHERE}
        GROUP BY platform_id
        HAVING game_count > 0
        """
    )
    for row in rows:
        window.setProperty(f"{PROPERTY_PREFIX}{row['platform_id']}", "1")
    has_games = bool(
        db.rows(
            f"""
            SELECT 1 FROM games
            WHERE {_VALID_GAMES_WHERE}
            LIMIT 1
            """
        )
    )
    window.setProperty("ZiroGames.HasLibrary", "1" if has_games else "0")
    if xbmc.getCondVisibility("System.HasAddon(plugin.program.ziro.games)"):
        xbmc.log(
            f"[Ziro Games] home platforms refreshed count={len(rows)} has_library={has_games}",
            xbmc.LOGINFO,
        )
