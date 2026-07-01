from __future__ import annotations

import os

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from .app_title import app_title
from .db import GameDatabase
from .titles import display_title

SKIN_IDS = ("skin.estuary.ziro",)
DIALOG_XML = "Custom_1110_DialogZiroGameInfo.xml"
RES_FOLDERS = ("xml", "1080i", "720p")
APP_NAME = app_title()


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
        title = display_title(game.get("title", ""), rom_path=game.get("rom_path", ""))
        self.setProperty("ZiroGame.Id", str(game.get("id") or ""))
        self.setProperty("ZiroGame.Title", title)
        self.setProperty("ZiroGame.Plot", game.get("description") or "")
        self.setProperty("ZiroGame.Platform", game.get("platform") or game.get("platform_id") or "")
        self.setProperty("ZiroGame.Year", str(game.get("release_year") or ""))
        self.setProperty("ZiroGame.Developer", game.get("developer") or "")
        self.setProperty("ZiroGame.Publisher", game.get("publisher") or "")
        self.setProperty("ZiroGame.Genre", game.get("genres") or "")
        self.setProperty("ZiroGame.PlayCount", str(game.get("play_count") or 0))
        self.setProperty("ZiroGame.Favorite", "1" if int(game.get("favorite") or 0) else "0")
        cover = (game.get("cover_path") or "").strip()
        self.setProperty("ZiroGame.Poster", cover if cover and xbmcvfs.exists(cover) else "")
        fanart = game.get("fanart_path") or ""
        screenshot = game.get("screenshot_path") or ""
        self.setProperty("ZiroGame.Fanart", fanart if fanart and xbmcvfs.exists(fanart) else "")
        self.setProperty("ZiroGame.Screenshot", screenshot if screenshot and xbmcvfs.exists(screenshot) else "")
        logo = game.get("logo_path") or screenshot or ""
        self.setProperty("ZiroGame.Logo", logo if logo and xbmcvfs.exists(logo) else "")
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
            title = display_title(self.game.get("title", ""), rom_path=self.game.get("rom_path", ""))
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
            if image and xbmcvfs.exists(image):
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
                cover = (refreshed.get("cover_path") or "").strip()
                self.setProperty("ZiroGame.Poster", cover if cover and xbmcvfs.exists(cover) else "")
                fanart = refreshed.get("fanart_path") or ""
                screenshot = refreshed.get("screenshot_path") or ""
                self.setProperty("ZiroGame.Fanart", fanart if fanart and xbmcvfs.exists(fanart) else "")
                self.setProperty("ZiroGame.Screenshot", screenshot if screenshot and xbmcvfs.exists(screenshot) else "")
                logo = refreshed.get("logo_path") or screenshot or ""
                self.setProperty("ZiroGame.Logo", logo if logo and xbmcvfs.exists(logo) else "")


def _dialog_xml_path(skin_root: str, res_folder: str) -> str:
    return os.path.join(skin_root, res_folder, DIALOG_XML)


def _resolve_skin_root(skin_root: str, seen: set[str]) -> tuple[str, str] | None:
    skin_root = xbmcvfs.translatePath(skin_root).rstrip("/\\")
    if not skin_root or skin_root in seen:
        return None
    seen.add(skin_root)
    if not xbmcvfs.exists(skin_root):
        return None
    for res_folder in RES_FOLDERS:
        if xbmcvfs.exists(_dialog_xml_path(skin_root, res_folder)):
            return skin_root, res_folder
    return None


def resolve_game_info_skin() -> tuple[str, str] | None:
    """Return (skin_root, res_folder) when the game info dialog XML is available."""
    seen: set[str] = set()

    for skin_id in SKIN_IDS:
        try:
            addon = xbmcaddon.Addon(skin_id)
            resolved = _resolve_skin_root(addon.getAddonInfo("path"), seen)
            if resolved:
                return resolved
        except Exception as exc:
            xbmc.log(f"[Games] skin lookup failed for {skin_id}: {exc}", xbmc.LOGDEBUG)

    return _resolve_skin_root("special://skin/", seen)


def show_game_info(game_id: int) -> None:
    db = GameDatabase()
    game = db.get_game(game_id)
    if not game:
        xbmcgui.Dialog().notification(APP_NAME, "Game not found", xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    resolved = resolve_game_info_skin()
    if not resolved:
        xbmcgui.Dialog().ok(
            APP_NAME,
            "Estuary Ziro is required for the game info screen.\n\n"
            "Install skin.estuary.ziro, set it as the active skin, then try again.",
        )
        return

    skin_path, res_folder = resolved
    dialog = ZiroGameInfoDialog(DIALOG_XML, skin_path, "Default", res_folder, game)
    dialog.doModal()
    del dialog
