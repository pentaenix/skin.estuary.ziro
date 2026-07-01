from __future__ import annotations

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from .db import GameDatabase

SKIN_ID = "skin.estuary.ziro"
DIALOG_XML = "Custom_1110_DialogZiroGameInfo.xml"


class ZiroGameInfoDialog(xbmcgui.WindowXMLDialog):
    def __init__(
        self,
        xml_name: str,
        script_path: str,
        default_skin: str,
        default_res: str,
        game: dict,
    ) -> None:
        super().__init__(str(xml_name), str(script_path), str(default_skin), str(default_res))
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
        fanart = game.get("fanart_path") or ""
        screenshot = game.get("screenshot_path") or ""
        self.setProperty("ZiroGame.Fanart", fanart)
        self.setProperty("ZiroGame.Screenshot", screenshot)
        logo = game.get("logo_path") or screenshot or ""
        self.setProperty("ZiroGame.Logo", logo)
        rating = game.get("rating")
        self.setProperty("ZiroGame.Rating", str(rating) if rating not in (None, "", 0) else "")

    def onClick(self, control_id: int) -> None:
        game_id = int(self.game["id"])
        if control_id == 8:
            self.close()
            xbmc.executebuiltin(f"RunScript(script.ziro.games.launcher,game_id={game_id})")
        elif control_id == 11:
            video_path = self.game.get("video_path") or ""
            if video_path and xbmcvfs.exists(video_path):
                xbmc.Player().play(video_path)
                return
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
            image = (
                self.game.get("fanart_path")
                or self.game.get("screenshot_path")
                or self.game.get("cover_path")
                or ""
            )
            if image:
                xbmcgui.Window(10000).setProperty("infobackground", image)
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
        elif control_id == 10:
            xbmc.executebuiltin(f"RunPlugin(plugin://plugin.program.ziro.games/?path=/choose_art&game_id={game_id})")
            refreshed = GameDatabase().get_game(game_id)
            if refreshed:
                self.game = refreshed
                self.setProperty("ZiroGame.Poster", refreshed.get("cover_path") or "")
                self.setProperty("ZiroGame.Fanart", refreshed.get("fanart_path") or "")
                self.setProperty("ZiroGame.Screenshot", refreshed.get("screenshot_path") or "")
                self.setProperty("ZiroGame.Logo", refreshed.get("logo_path") or refreshed.get("screenshot_path") or "")


def show_game_info(game_id: int) -> None:
    db = GameDatabase()
    game = db.get_game(game_id)
    if not game:
        xbmcgui.Dialog().notification("Ziro Games", "Game not found", xbmcgui.NOTIFICATION_ERROR, 3000)
        return
    try:
        skin = xbmcaddon.Addon(SKIN_ID)
        skin_path = xbmc.translatePath(skin.getAddonInfo("path"))
    except Exception:
        xbmcgui.Dialog().ok("Ziro Games", "Estuary Ziro skin is required for the game info screen.")
        return
    if not xbmcvfs.exists(skin_path):
        xbmcgui.Dialog().ok("Ziro Games", "Estuary Ziro skin path is not available.")
        return
    dialog = ZiroGameInfoDialog(str(DIALOG_XML), skin_path, "xml", "1080i", game)
    dialog.doModal()
    del dialog
