from __future__ import annotations

import json
import os
from datetime import datetime

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from .app_title import app_title
from .art_paths import usable_art_path
from .db import GameDatabase
from .metadata.local_metadata import lookup_local_metadata
from .text_utils import clean_display_text
from .titles import display_title

SKIN_IDS = ("skin.estuary.ziro",)
DIALOG_XML = "Custom_1110_DialogZiroGameInfo.xml"
RES_FOLDERS = ("xml", "1080i", "720p")
POSTER_CONTROL_ID = 200
LOGO_CONTROL_ID = 201
APP_NAME = app_title()

GAME_DETAIL_SQL = """
SELECT g.*, p.name AS platform,
       COALESCE(group_concat(ge.name, ', '), '') AS genres,
       s.folder_path AS source_folder
FROM games g
LEFT JOIN platforms p ON p.id = g.platform_id
LEFT JOIN game_genres gg ON gg.game_id = g.id
LEFT JOIN genres ge ON ge.id = gg.genre_id
LEFT JOIN sources s ON s.id = g.source_id
WHERE g.id=? AND g.hidden=0
GROUP BY g.id
"""


class ZiroGameInfoDialog(xbmcgui.WindowXMLDialog):
    _game: dict = {}

    def __init__(
        self,
        xml_name: str,
        script_path: str,
        default_skin: str = "",
        default_res: str = "xml",
    ) -> None:
        super().__init__(str(xml_name), str(script_path), str(default_skin), str(default_res))

    @classmethod
    def set_game(cls, game: dict) -> None:
        cls._game = game

    def onInit(self) -> None:
        self._apply_properties(self._game)

    def _apply_properties(self, game: dict) -> None:
        title = display_title(game.get("title", ""), rom_path=game.get("rom_path", ""))
        art = _resolve_art_for_game(game)
        self.setProperty("ZiroGame.Id", str(game.get("id") or ""))
        self.setProperty("ZiroGame.Title", title)
        self.setProperty("ZiroGame.Plot", clean_display_text(game.get("description") or ""))
        self.setProperty("ZiroGame.Platform", game.get("platform") or game.get("platform_id") or "")
        self.setProperty("ZiroGame.Year", str(game.get("release_year") or ""))
        self.setProperty("ZiroGame.Developer", game.get("developer") or "")
        self.setProperty("ZiroGame.Publisher", game.get("publisher") or "")
        self.setProperty("ZiroGame.Genre", game.get("genres") or "")
        play_count = int(game.get("play_count") or 0)
        self.setProperty("ZiroGame.PlayCount", str(play_count) if play_count else "")
        self.setProperty("ZiroGame.LastPlayed", _format_last_played(game.get("last_played") or ""))
        self.setProperty("ZiroGame.Favorite", "1" if int(game.get("favorite") or 0) else "0")
        self.setProperty("ZiroGame.Poster", art.get("cover_path", ""))
        self.setProperty("ZiroGame.Fanart", art.get("fanart_path", ""))
        self.setProperty("ZiroGame.Screenshot", art.get("screenshot_path", ""))
        self.setProperty("ZiroGame.Logo", art.get("logo_path", ""))
        self.setProperty("ZiroGame.Video", art.get("video_path", ""))
        self.setProperty("ZiroGame.HasPoster", "1" if art.get("cover_path") else "")
        self.setProperty("ZiroGame.HasLogo", "1" if art.get("logo_path") else "")
        self.setProperty("ZiroGame.HasFanart", "1" if art.get("fanart_path") else "")
        self.setProperty("ZiroGame.HasScreenshot", "1" if art.get("screenshot_path") else "")
        xbmc.log(
            f"[Games] game info art game_id={game.get('id')} poster={art.get('cover_path', '')}",
            xbmc.LOGINFO,
        )
        self._set_dialog_images(art)
        rating = game.get("rating")
        self.setProperty("ZiroGame.Rating", str(rating) if rating not in (None, "", 0) else "")
        background = art.get("fanart_path") or art.get("screenshot_path") or art.get("cover_path") or ""
        if background:
            xbmcgui.Window(10000).setProperty("infobackground", background)

    def _set_dialog_images(self, art: dict) -> None:
        poster = art.get("cover_path", "")
        logo = art.get("logo_path", "")
        try:
            self.getControl(POSTER_CONTROL_ID).setImage(poster)
        except RuntimeError as exc:
            xbmc.log(f"[Games] poster setImage failed: {exc}", xbmc.LOGWARNING)
        try:
            self.getControl(LOGO_CONTROL_ID).setImage(logo if logo else "")
        except RuntimeError as exc:
            xbmc.log(f"[Games] logo setImage failed: {exc}", xbmc.LOGWARNING)

    def onClick(self, control_id: int) -> None:
        game_id = int(self._game["id"])
        if control_id == 8:
            self.close()
            xbmc.executebuiltin(f"RunScript(script.ziro.games.launcher,game_id={game_id})")
        elif control_id in {11, 110}:
            video_path = usable_art_path(self._game.get("video_path") or "")
            if video_path:
                xbmc.Player().play(video_path)
                return
            title = display_title(self._game.get("title", ""), rom_path=self._game.get("rom_path", ""))
            if xbmc.getCondVisibility("System.HasAddon(script.extendedinfo)"):
                xbmc.executebuiltin(
                    f'RunScript(script.extendedinfo,info=youtubebrowser,id={title} trailer)'
                )
            else:
                xbmc.executebuiltin(
                    f'PlayMedia(plugin://plugin.video.youtube/?action=search_query&search={title} trailer)'
                )
        elif control_id == 102:
            art = _resolve_art_for_game(self._game)
            image = art.get("fanart_path") or art.get("screenshot_path") or art.get("cover_path") or ""
            if image:
                xbmcgui.Window(10000).setProperty("infobackground", image)
                xbmc.executebuiltin("ActivateWindow(1104)")
        elif control_id == 7:
            db = GameDatabase()
            db.execute(
                "UPDATE games SET favorite = CASE favorite WHEN 1 THEN 0 ELSE 1 END WHERE id=?",
                (game_id,),
            )
            self._game["favorite"] = 0 if int(self._game.get("favorite") or 0) else 1
            self.setProperty("ZiroGame.Favorite", "1" if self._game["favorite"] else "0")
        elif control_id == 6:
            xbmc.executebuiltin(f"RunPlugin(plugin://plugin.program.ziro.games/?path=/refresh&game_id={game_id})")
            refreshed = _load_game_details(game_id)
            if refreshed:
                self._game = refreshed
                ZiroGameInfoDialog._game = refreshed
                self._apply_properties(refreshed)
        elif control_id == 10:
            xbmc.executebuiltin(f"RunPlugin(plugin://plugin.program.ziro.games/?path=/choose_art&game_id={game_id})")
            refreshed = _load_game_details(game_id)
            if refreshed:
                self._game = refreshed
                ZiroGameInfoDialog._game = refreshed
                self._apply_properties(refreshed)


def _format_last_played(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value[:16]


def _load_game_details(game_id: int) -> dict | None:
    db = GameDatabase()
    game = db.one(GAME_DETAIL_SQL, (game_id,))
    if not game:
        return None
    return _merge_local_metadata(game)


def _merge_local_metadata(game: dict) -> dict:
    merged = dict(game)
    local = lookup_local_metadata(
        merged.get("rom_path") or "",
        source_folder=merged.get("source_folder") or "",
        platform_id=merged.get("platform_id") or "",
    )
    for field in (
        "description",
        "developer",
        "publisher",
        "release_year",
        "cover_path",
        "fanart_path",
        "logo_path",
        "screenshot_path",
        "video_path",
        "genres",
    ):
        if local.get(field) and not merged.get(field):
            merged[field] = local[field]
    if local.get("genres") and not merged.get("genres"):
        merged["genres"] = local["genres"]
    return merged


def _resolve_art_for_game(game: dict) -> dict[str, str]:
    fields = ("cover_path", "fanart_path", "logo_path", "screenshot_path", "video_path")
    resolved: dict[str, str] = {}
    for field in fields:
        path = usable_art_path(game.get(field) or "", trust_if_plausible=True)
        if path:
            resolved[field] = path

    local = lookup_local_metadata(
        game.get("rom_path") or "",
        source_folder=game.get("source_folder") or "",
        platform_id=game.get("platform_id") or "",
    )
    for field in fields:
        if not resolved.get(field):
            path = usable_art_path(local.get(field) or "", trust_if_plausible=True)
            if path:
                resolved[field] = path

    if resolved.get("screenshot_path") and not resolved.get("logo_path"):
        resolved["logo_path"] = resolved["screenshot_path"]
    return resolved


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

    return targets


def show_game_info(game_id: int) -> None:
    game = _load_game_details(game_id)
    if not game:
        xbmcgui.Dialog().notification(APP_NAME, "Game not found", xbmcgui.NOTIFICATION_ERROR, 3000)
        return

    active_skin_id = _current_skin_id()
    last_error = ""
    ZiroGameInfoDialog.set_game(game)
    for skin_path, res_folder in resolve_game_info_targets():
        try:
            dialog = ZiroGameInfoDialog(DIALOG_XML, skin_path, "", res_folder)
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
