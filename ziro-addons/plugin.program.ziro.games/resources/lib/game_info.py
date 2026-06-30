from __future__ import annotations

import xbmc
import xbmcaddon
import xbmcgui

from .db import GameDatabase

SKIN_ID = "skin.estuary.ziro"
DIALOG_XML = "Custom_1110_DialogZiroGameInfo.xml"


class ZiroGameInfoDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, game: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.game = game

    def onInit(self) -> None:
        game = self.game
        self.setProperty("ZiroGame.Id", str(game.get("id") or ""))
        self.setProperty("ZiroGame.Title", game.get("title") or "")
        self.setProperty("ZiroGame.Plot", game.get("description") or "")
        self.setProperty("ZiroGame.Platform", game.get("platform") or game.get("platform_id") or "")
        self.setProperty("ZiroGame.Year", str(game.get("release_year") or ""))
        self.setProperty("ZiroGame.Developer", game.get("developer") or "")
        self.setProperty("ZiroGame.Publisher", game.get("publisher") or "")
        self.setProperty("ZiroGame.Genre", game.get("genres") or "")
        self.setProperty("ZiroGame.PlayCount", str(game.get("play_count") or 0))
        self.setProperty("ZiroGame.Favorite", "1" if int(game.get("favorite") or 0) else "0")
        self.setProperty("ZiroGame.Poster", game.get("cover_path") or "")
        self.setProperty("ZiroGame.Fanart", game.get("fanart_path") or "")
        self.setProperty("ZiroGame.Logo", game.get("logo_path") or "")
        rating = game.get("rating")
        self.setProperty("ZiroGame.Rating", str(rating) if rating not in (None, "", 0) else "")

    def onClick(self, control_id: int) -> None:
        game_id = int(self.game["id"])
        if control_id == 8:
            self.close()
            xbmc.executebuiltin(f"RunScript(script.ziro.games.launcher,game_id={game_id})")
        elif control_id == 11:
            title = self.game.get("title") or ""
            if xbmc.getCondVisibility("System.HasAddon(script.extendedinfo)"):
                xbmc.executebuiltin(
                    f'RunScript(script.extendedinfo,info=youtubebrowser,id={title} trailer)'
                )
            else:
                xbmc.executebuiltin(
                    f'PlayMedia(plugin://plugin.video.youtube/?action=search_query&search={title} trailer)'
                )
        elif control_id == 102:
            fanart = self.game.get("fanart_path") or self.game.get("cover_path") or ""
            if fanart:
                self.setProperty("infobackground", fanart, "home")
                xbmc.executebuiltin("ActivateWindow(1104)")
        elif control_id == 7:
            db = GameDatabase()
            db.execute(
                "UPDATE games SET favorite = CASE favorite WHEN 1 THEN 0 ELSE 1 END WHERE id=?",
                (game_id,),
            )
            self.game["favorite"] = 0 if int(self.game.get("favorite") or 0) else 1
            self.setProperty("ZiroGame.Favorite", "1" if self.game["favorite"] else "0")
        elif control_id == 6:
            xbmc.executebuiltin(f"RunPlugin(plugin://plugin.program.ziro.games/?path=/refresh&game_id={game_id})")


def show_game_info(game_id: int) -> None:
    db = GameDatabase()
    game = db.get_game(game_id)
    if not game:
        xbmcgui.Dialog().notification("Ziro Games", "Game not found", xbmcgui.NOTIFICATION_ERROR, 3000)
        return
    try:
        skin = xbmcaddon.Addon(SKIN_ID)
        skin_path = skin.getAddonInfo("path")
    except Exception:
        xbmcgui.Dialog().ok("Ziro Games", "Estuary Ziro skin is required for the game info screen.")
        return
    dialog = ZiroGameInfoDialog(game, DIALOG_XML, skin_path, "xml")
    dialog.doModal()
    del dialog
