from __future__ import annotations

import json
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


def _normalize_path(path: str) -> str:
    path = xbmcvfs.translatePath(path or "").strip()
    if not path:
        return ""
    return path.replace("\\", "/")


def _path_exists(path: str) -> bool:
    normalized = _normalize_path(path)
    if not normalized:
        return False
    if xbmcvfs.exists(normalized):
        return True
    os_path = os.path.normpath(normalized)
    return os.path.isfile(os_path) or os.path.isdir(os_path)


def _skin_id_from_path(skin_root: str) -> str:
    normalized = _normalize_path(skin_root).rstrip("/")
    return normalized.rsplit("/", 1)[-1] if normalized else ""


def _current_skin_id() -> str:
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "Settings.GetSettingValue",
            "params": {"setting": "lookandfeel.skin"},
            "id": 1,
        }
        response = json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
        value = response.get("result", {}).get("value")
        if isinstance(value, dict):
            skin_id = str(value.get("value") or "").strip()
            if skin_id:
                return skin_id
    except Exception as exc:
        xbmc.log(f"[Games] skin setting lookup failed: {exc}", xbmc.LOGDEBUG)

    return _skin_id_from_path(_normalize_path("special://skin/"))


def _candidate_skin_roots() -> list[str]:
    roots: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        root = _normalize_path(path).rstrip("/")
        if root and root not in seen:
            seen.add(root)
            roots.append(root)

    try:
        add(xbmc.getSkinDir())
    except Exception:
        pass
    add("special://skin/")
    add("special://addons/skin.estuary.ziro/")
    for skin_id in SKIN_IDS:
        try:
            add(xbmcaddon.Addon(skin_id).getAddonInfo("path"))
        except Exception:
            pass
    return roots


def _dialog_xml_path(skin_root: str, res_folder: str) -> str:
    return f"{skin_root.rstrip('/')}/{res_folder}/{DIALOG_XML}"


def resolve_game_info_targets() -> list[tuple[str, str]]:
    """Return skin roots and resolution folders to try for the game info dialog."""
    targets: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    active_skin_id = _current_skin_id()

    def add_target(skin_root: str, res_folder: str) -> None:
        root = _normalize_path(skin_root).rstrip("/")
        if not root:
            return
        key = (root, res_folder)
        if key in seen:
            return
        seen.add(key)
        targets.append(key)

    for skin_root in _candidate_skin_roots():
        for res_folder in RES_FOLDERS:
            if _path_exists(_dialog_xml_path(skin_root, res_folder)):
                add_target(skin_root, res_folder)

    if active_skin_id in SKIN_IDS:
        for skin_root in _candidate_skin_roots():
            if _skin_id_from_path(skin_root) != active_skin_id and active_skin_id not in skin_root:
                continue
            if _path_exists(skin_root):
                add_target(skin_root, "xml")
                for res_folder in RES_FOLDERS[1:]:
                    add_target(skin_root, res_folder)

    if not targets:
        for skin_root in _candidate_skin_roots():
            if _path_exists(skin_root):
                add_target(skin_root, "xml")
                break

    if targets:
        xbmc.log(
            f"[Games] game info targets for skin={active_skin_id}: {targets}",
            xbmc.LOGINFO,
        )
    else:
        xbmc.log(
            f"[Games] no game info targets found for skin={active_skin_id}; roots={_candidate_skin_roots()}",
            xbmc.LOGWARNING,
        )
    return targets


def show_game_info(game_id: int) -> None:
    db = GameDatabase()
    game = db.get_game(game_id)
    if not game:
        xbmcgui.Dialog().notification(APP_NAME, "Game not found", xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    active_skin_id = _current_skin_id()
    last_error = ""
    for skin_path, res_folder in resolve_game_info_targets():
        try:
            dialog = ZiroGameInfoDialog(DIALOG_XML, skin_path, "", res_folder, game)
            dialog.doModal()
            del dialog
            return
        except Exception as exc:
            last_error = str(exc)
            xbmc.log(
                f"[Games] game info open failed ({skin_path}/{res_folder}): {exc}",
                xbmc.LOGWARNING,
            )

    if active_skin_id in SKIN_IDS:
        message = (
            "Could not open the game info dialog.\n\n"
            f"Active skin: {active_skin_id}\n"
            f"Missing file: xml/{DIALOG_XML}\n\n"
            "Re-run dev_deploy_to_kodi.bat, restart Kodi, then try again."
        )
    else:
        message = (
            "Estuary Ziro is required for the game info screen.\n\n"
            f"Active skin: {active_skin_id or 'unknown'}\n"
            "Set skin.estuary.ziro as the active skin, then try again."
        )
    if last_error:
        message += f"\n\nDetails: {last_error}"
    xbmcgui.Dialog().ok(APP_NAME, message)
