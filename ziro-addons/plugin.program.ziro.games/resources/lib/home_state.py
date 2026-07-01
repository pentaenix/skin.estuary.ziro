from __future__ import annotations

import xbmc
import xbmcgui

from .db import GameDatabase
from .platforms import platform_ids

HOME_WINDOW_ID = 10000
PLATFORM_PROPERTY_PREFIX = "ZiroGames.Platform."
GENRE_PROPERTY_PREFIX = "ZiroGames.Genre."

GENRE_IDS = ("rpg", "platformer", "adventure", "racing", "fighting", "coop")

HOME_WIDGET_LIST_IDS = (
    17300,
    17310,
    17320,
    *range(17510, 17780, 10),
)

_VALID_GAMES_WHERE = """
    hidden = 0
    AND LENGTH(TRIM(title)) > 0
    AND rom_path NOT LIKE 'mock://%'
    AND rom_path NOT LIKE 'test://%'
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
    refresh_home_properties(db)


def refresh_home_properties(db: GameDatabase | None = None) -> None:
    db = db or GameDatabase()
    window = xbmcgui.Window(HOME_WINDOW_ID)
    for platform_id in platform_ids():
        window.clearProperty(f"{PLATFORM_PROPERTY_PREFIX}{platform_id}")
    for genre_id in GENRE_IDS:
        window.clearProperty(f"{GENRE_PROPERTY_PREFIX}{genre_id}")

    platform_rows = db.rows(
        f"""
        SELECT platform_id, COUNT(*) AS game_count
        FROM games
        WHERE {_VALID_GAMES_WHERE}
        GROUP BY platform_id
        HAVING game_count > 0
        """
    )
    for row in platform_rows:
        window.setProperty(f"{PLATFORM_PROPERTY_PREFIX}{row['platform_id']}", "1")

    genre_rows = db.rows(
        f"""
        SELECT gg.genre_id, COUNT(*) AS game_count
        FROM game_genres gg
        INNER JOIN games g ON g.id = gg.game_id
        WHERE g.hidden = 0
          AND LENGTH(TRIM(g.title)) > 0
          AND g.rom_path NOT LIKE '%ziro-addons%'
          AND g.rom_path NOT LIKE '%skin.estuary.ziro%'
          AND g.rom_path NOT LIKE '%plugin.program.ziro.games%'
          AND g.rom_path NOT LIKE '%/dist/%'
          AND g.rom_path NOT LIKE '%\\dist\\%'
          AND g.title NOT LIKE '%.zip'
          AND g.title NOT LIKE '%plugin.program%'
          AND g.title NOT LIKE '%script.ziro%'
        GROUP BY gg.genre_id
        HAVING game_count > 0
        """
    )
    for row in genre_rows:
        window.setProperty(f"{GENRE_PROPERTY_PREFIX}{row['genre_id']}", "1")

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
            f"[Ziro Games] home refreshed platforms={len(platform_rows)} genres={len(genre_rows)} has_library={has_games}",
            xbmc.LOGINFO,
        )


def refresh_home_widgets(db: GameDatabase | None = None) -> None:
    refresh_home_properties(db)
    window = xbmcgui.Window(HOME_WINDOW_ID)
    token = str(int(window.getProperty("ZiroGames.RefreshToken") or "0") + 1)
    window.setProperty("ZiroGames.RefreshToken", token)
    if not xbmc.getCondVisibility("Window.IsActive(home)"):
        return
    for list_id in HOME_WIDGET_LIST_IDS:
        try:
            xbmc.executebuiltin(f"Container.Update({list_id},replace)")
        except Exception:
            pass
