# -*- coding: utf-8 -*-
from __future__ import annotations

import xbmc
import xbmcgui

from resources.lib.app_title import app_title
from resources.lib.cache import clear_downloaded_artwork, refresh_games_ui
from resources.lib.db import GameDatabase


def run() -> None:
    app = app_title()
    if not xbmcgui.Dialog().yesno(
        app,
        "Clear downloaded artwork from SteamGridDB and ScreenScraper?\n\n"
        "Images stored next to your ROMs (Skraper) are kept.",
    ):
        return
    db = GameDatabase()
    result = clear_downloaded_artwork(db)
    refresh_games_ui(db)
    xbmcgui.Dialog().ok(app, result.summary())


if __name__ == "__main__":
    run()
