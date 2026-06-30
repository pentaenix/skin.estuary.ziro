from __future__ import annotations

import xbmc
import xbmcgui

from .db import GameDatabase
from .platforms import platform_ids

HOME_WINDOW_ID = 10000
PROPERTY_PREFIX = "ZiroGames.Platform."


def refresh_home_platform_properties(db: GameDatabase | None = None) -> None:
    db = db or GameDatabase()
    window = xbmcgui.Window(HOME_WINDOW_ID)
    for platform_id in platform_ids():
        window.clearProperty(f"{PROPERTY_PREFIX}{platform_id}")
    rows = db.rows("SELECT DISTINCT platform_id FROM games WHERE hidden = 0")
    for row in rows:
        window.setProperty(f"{PROPERTY_PREFIX}{row['platform_id']}", "1")
    has_games = bool(db.rows("SELECT 1 FROM games WHERE hidden = 0 LIMIT 1"))
    window.setProperty("ZiroGames.HasLibrary", "1" if has_games else "0")
    if xbmc.getCondVisibility("System.HasAddon(plugin.program.ziro.games)"):
        xbmc.log(
            f"[Ziro Games] home platforms refreshed count={len(rows)} has_library={has_games}",
            xbmc.LOGINFO,
        )
