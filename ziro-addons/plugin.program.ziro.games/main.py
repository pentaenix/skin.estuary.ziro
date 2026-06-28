from __future__ import annotations

import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.db import GameDatabase
from resources.lib.routes import Router
from resources.lib.scanner import SYSTEMS

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def plugin_url(path: str, **query: str) -> str:
    qs = urlencode(query)
    return f"{BASE_URL}?path={path}" + (f"&{qs}" if qs else "")


def add_directory(label: str, path: str, art: dict[str, str] | None = None) -> None:
    item = xbmcgui.ListItem(label=label)
    item.setProperty("IsPlayable", "false")
    if art:
        item.setArt(art)
    xbmcplugin.addDirectoryItem(HANDLE, plugin_url(path), item, True)


def add_action(label: str, path: str, art: dict[str, str] | None = None) -> None:
    item = xbmcgui.ListItem(label=label)
    item.setProperty("IsPlayable", "false")
    if art:
        item.setArt(art)
    xbmcplugin.addDirectoryItem(HANDLE, plugin_url(path), item, False)


def add_source_item(source: dict) -> None:
    label = f"{source.get('platform_name') or source['platform_id']}: {source['folder_path']}"
    item = xbmcgui.ListItem(label=label)
    item.setProperty("IsPlayable", "false")
    item.setInfo("video", {
        "title": label,
        "plot": "Game source folder. Use the context menu to remove it.",
    })
    item.addContextMenuItems([
        ("Remove source", f"RunPlugin({plugin_url('/sources/remove', source_id=str(source['id']))})"),
    ])
    xbmcplugin.addDirectoryItem(HANDLE, plugin_url("/sources"), item, False)


def add_game(game: dict) -> None:
    item = xbmcgui.ListItem(label=game["title"])
    item.setProperty("IsPlayable", "true")
    art = {
        "thumb": game.get("cover_path") or "DefaultProgram.png",
        "poster": game.get("cover_path") or "DefaultProgram.png",
        "fanart": game.get("fanart_path") or "",
        "clearlogo": game.get("logo_path") or "",
    }
    item.setArt({k: v for k, v in art.items() if v})
    info = {
        "title": game.get("title", ""),
        "plot": game.get("description", ""),
        "year": int(game["release_year"]) if game.get("release_year") else 0,
        "genre": game.get("genres", ""),
    }
    try:
        item.setInfo("game", info)
    except Exception:
        item.setInfo("video", info)
    item.addContextMenuItems([
        ("Toggle favorite", f"RunPlugin({plugin_url('/favorite', game_id=str(game['id']))})"),
        ("Refresh metadata", f"RunPlugin({plugin_url('/refresh', game_id=str(game['id']))})"),
    ])
    xbmcplugin.addDirectoryItem(HANDLE, plugin_url("/launch", game_id=str(game["id"])), item, False)


def render_message(label: str, message: str) -> None:
    item = xbmcgui.ListItem(label=label)
    item.setProperty("IsPlayable", "false")
    item.setInfo("video", {"title": label, "plot": message})
    xbmcplugin.addDirectoryItem(HANDLE, plugin_url("/settings"), item, False)


def render_game_list(games: list[dict], empty_label: str = "No games yet") -> None:
    if not games:
        render_message(empty_label, "Add one or more game source folders, then run Scan / Refresh Library.")
    for game in games:
        add_game(game)
    xbmcplugin.setContent(HANDLE, "games")
    xbmcplugin.endOfDirectory(HANDLE)


def browse_for_source(platform_id: str) -> str:
    platform_name = {
        "gamecube": "Nintendo GameCube",
        "wii": "Nintendo Wii",
        "gba": "Game Boy Advance",
    }.get(platform_id, platform_id)
    heading = f"Choose {platform_name} folder"
    # Type 0 is directory browse. This is closer to Kodi's Movies source flow than raw settings strings.
    selected = xbmcgui.Dialog().browse(0, heading, "files", "", False, False, "")
    return selected or ""


def main() -> None:
    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 else {}
    path = params.get("path", "/home")
    db = GameDatabase()
    router = Router(db)

    try:
        if path == "/home":
            add_directory("Continue Playing", "/continue")
            add_directory("Recently Added", "/recent")
            add_directory("Favorites", "/favorites")
            add_directory("Platforms", "/platforms")
            add_directory("Genres", "/genres")
            add_directory("Sources", "/sources")
            add_action("Scan / Refresh Library", "/scan")
            add_action("Settings", "/settings")
            xbmcplugin.setContent(HANDLE, "files")
            xbmcplugin.endOfDirectory(HANDLE)
        elif path == "/continue":
            render_game_list(router.continue_playing(), "Nothing in Continue Playing")
        elif path == "/recent":
            render_game_list(router.recently_added(), "No recently added games")
        elif path == "/favorites":
            render_game_list(router.favorites(), "No favorite games")
        elif path == "/platforms":
            for platform in router.platforms():
                add_directory(platform["name"], f"/platform/{platform['id']}")
            xbmcplugin.endOfDirectory(HANDLE)
        elif path.startswith("/platform/"):
            platform_id = path.rsplit("/", 1)[-1]
            render_game_list(router.by_platform(platform_id), "No games for this platform")
        elif path == "/genres":
            for genre in router.genres():
                add_directory(genre["name"], f"/genre/{genre['id']}")
            xbmcplugin.endOfDirectory(HANDLE)
        elif path.startswith("/genre/"):
            genre_id = path.rsplit("/", 1)[-1]
            render_game_list(router.by_genre(genre_id), "No games for this genre")
        elif path == "/sources":
            add_directory("Add Nintendo GameCube Source", "/sources/add/gamecube")
            add_directory("Add Nintendo Wii Source", "/sources/add/wii")
            add_directory("Add Game Boy Advance Source", "/sources/add/gba")
            for source in router.sources():
                add_source_item(source)
            xbmcplugin.setContent(HANDLE, "files")
            xbmcplugin.endOfDirectory(HANDLE)
        elif path.startswith("/sources/add/"):
            platform_id = path.rsplit("/", 1)[-1]
            if platform_id not in SYSTEMS:
                raise ValueError(f"Unsupported platform: {platform_id}")
            selected = browse_for_source(platform_id)
            if selected:
                router.add_source(platform_id, selected)
                xbmcgui.Dialog().notification("Ziro Games", "Source added", xbmcgui.NOTIFICATION_INFO, 2500)
                if xbmcgui.Dialog().yesno("Ziro Games", "Source added. Scan now?"):
                    count = router.scan_sources()
                    xbmcgui.Dialog().notification("Ziro Games", f"Scan complete: {count} games", xbmcgui.NOTIFICATION_INFO, 3000)
                xbmc.executebuiltin("Container.Refresh")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/sources/remove":
            source_id = int(params["source_id"])
            if xbmcgui.Dialog().yesno("Ziro Games", "Remove this source?", "Games imported from it will be hidden, not deleted from disk."):
                router.remove_source(source_id)
                xbmcgui.Dialog().notification("Ziro Games", "Source removed", xbmcgui.NOTIFICATION_INFO, 2500)
                xbmc.executebuiltin("Container.Refresh")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/launch":
            game_id = params.get("game_id")
            if not game_id:
                raise ValueError("Missing game_id")
            xbmc.executebuiltin(f"RunScript(script.ziro.games.launcher,game_id={game_id})")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/favorite":
            router.toggle_favorite(int(params["game_id"]))
            xbmcgui.Dialog().notification("Ziro Games", "Favorite updated", xbmcgui.NOTIFICATION_INFO, 2000)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/refresh":
            xbmcgui.Dialog().notification("Ziro Games", "Metadata refresh is scaffolded for the next pass", xbmcgui.NOTIFICATION_INFO, 2500)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/scan":
            count = router.scan_sources()
            xbmcgui.Dialog().notification("Ziro Games", f"Scan complete: {count} games", xbmcgui.NOTIFICATION_INFO, 3000)
            xbmc.executebuiltin("Container.Refresh")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/settings":
            ADDON.openSettings()
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        else:
            raise ValueError(f"Unknown route: {path}")
    except Exception as exc:
        xbmc.log(f"[Ziro Games] route failed path={path}: {exc}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Ziro Games", str(exc), xbmcgui.NOTIFICATION_ERROR, 5000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


if __name__ == "__main__":
    main()
