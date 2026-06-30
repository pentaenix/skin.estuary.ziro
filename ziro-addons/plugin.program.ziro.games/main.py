from __future__ import annotations

import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.db import GameDatabase
from resources.lib.game_info import show_game_info
from resources.lib.home_state import refresh_home_platform_properties
from resources.lib.metadata.platform_art import get_platform_art_path
from resources.lib.paths_filter import is_allowed_source_folder
from resources.lib.platforms import get_platform, platform_choices
from resources.lib.routes import Router
from resources.lib.scan_jobs import scan_in_background

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]

LIBRARY_ICONS: dict[str, str] = {
    "/continue": "DefaultInProgressShows.png",
    "/recent": "DefaultRecentlyAddedEpisodes.png",
    "/favorites": "DefaultFavourites.png",
    "/genres": "DefaultGenres.png",
    "/sources": "DefaultFolder.png",
    "/all": "DefaultMovies.png",
}


def add_library_entry(
    label: str,
    path: str,
    label2: str = "",
    *,
    icon: str | None = None,
    badge: str = "",
) -> None:
    item = xbmcgui.ListItem(label=label, label2=label2)
    item.setProperty("IsPlayable", "false")
    if badge:
        item.setProperty("ziro_platform_badge", badge)
    icon_path = icon or LIBRARY_ICONS.get(path, "DefaultFolder.png")
    if badge:
        icon_path = "DefaultFolder.png"
    item.setArt({"icon": icon_path, "thumb": icon_path})
    item.setInfo("video", {"title": label, "plot": label2, "genre": label2})
    xbmcplugin.addDirectoryItem(HANDLE, plugin_url(path), item, True)


def add_platform_directory(platform: dict, path: str, label2: str = "") -> None:
    platform_id = platform["id"]
    art_path = get_platform_art_path(platform_id, allow_fetch=True)
    art = {
        "icon": art_path or "DefaultGames.png",
        "thumb": art_path or "DefaultGames.png",
        "poster": art_path or "",
    }
    item = xbmcgui.ListItem(label=platform["name"], label2=label2)
    item.setProperty("IsPlayable", "false")
    item.setArt({k: v for k, v in art.items() if v})
    item.setInfo("video", {"title": platform["name"], "plot": label2})
    xbmcplugin.addDirectoryItem(HANDLE, plugin_url(path), item, True)


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


def _play_on_click() -> bool:
    return (ADDON.getSetting("game_click_action") or "info").strip().lower() == "play"


def _game_item_url(game_id: int) -> str:
    if _play_on_click():
        return plugin_url("/launch", game_id=str(game_id))
    return plugin_url("/info", game_id=str(game_id))


def add_game(game: dict) -> None:
    play_on_click = _play_on_click()
    item = xbmcgui.ListItem(label=game["title"])
    item.setProperty("IsPlayable", "true" if play_on_click else "false")
    item.setProperty("ziro_game_id", str(game["id"]))
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
        "platform": game.get("platform") or game.get("platform_id", ""),
        "developer": game.get("developer") or "",
        "publisher": game.get("publisher") or "",
        "playcount": int(game.get("play_count") or 0),
    }
    try:
        item.setInfo("game", info)
    except Exception:
        item.setInfo("video", info)
    item.addContextMenuItems([
        ("Play", f"RunScript(script.ziro.games.launcher,game_id={game['id']})"),
        ("Game info", f"RunPlugin({plugin_url('/info', game_id=str(game['id']))})"),
        ("Toggle favorite", f"RunPlugin({plugin_url('/favorite', game_id=str(game['id']))})"),
        ("Refresh metadata", f"RunPlugin({plugin_url('/refresh', game_id=str(game['id']))})"),
    ])
    xbmcplugin.addDirectoryItem(HANDLE, _game_item_url(int(game["id"])), item, False)


def render_library_menu(router: Router) -> None:
    add_library_entry("Continue Playing", "/continue")
    add_library_entry("Recently Added", "/recent")
    add_library_entry("Favorites", "/favorites")
    for platform in router.platforms():
        count = int(platform.get("game_count") or 0)
        badge = (platform.get("short_name") or platform["id"]).upper()
        add_library_entry(
            badge,
            f"/platform/{platform['id']}",
            f"{platform['name']} · {count} games",
            badge=badge,
        )
    add_library_entry("Genres", "/genres")
    add_library_entry("Sources", "/sources")
    add_library_entry("All Games", "/all")
    xbmcplugin.setContent(HANDLE, "games")
    xbmcplugin.endOfDirectory(HANDLE)


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


def browse_for_source(platform_name: str) -> str:
    heading = f"Choose {platform_name} folder"
    # Type 0 is directory browse. This is closer to Kodi's Movies source flow than raw settings strings.
    selected = xbmcgui.Dialog().browse(0, heading, "files", "", False, False, "")
    return selected or ""


def pick_platform_id() -> str | None:
    choices = platform_choices()
    labels = [choice["label"] for choice in choices]
    index = xbmcgui.Dialog().select("Select console", labels)
    if index < 0:
        return None
    return choices[index]["id"]


def open_addon_settings() -> None:
    addon_id = ADDON.getAddonInfo("id")
    xbmc.executebuiltin(f"Addon.OpenSettings({addon_id})")


def show_scan_result(result) -> None:
    summary = result.summary()
    headline = summary.splitlines()[0]
    if result.imported:
        xbmcgui.Dialog().notification("Ziro Games", headline, xbmcgui.NOTIFICATION_INFO, 4000)
        return
    xbmc.log(f"[Ziro Games Scanner] {summary}", xbmc.LOGWARNING)
    xbmcgui.Dialog().notification("Ziro Games", headline, xbmcgui.NOTIFICATION_WARNING, 5000)


def confirm_remove_source(router: Router, source_id: int) -> None:
    source = router.db.one(
        """
        SELECT s.*, p.name AS platform_name
        FROM sources s
        LEFT JOIN platforms p ON p.id = s.platform_id
        WHERE s.id=?
        """,
        (source_id,),
    )
    if not source:
        xbmcgui.Dialog().notification("Ziro Games", "Source not found", xbmcgui.NOTIFICATION_ERROR, 3000)
        return
    label = source.get("platform_name") or source["platform_id"]
    folder = source.get("folder_path") or ""
    if not xbmcgui.Dialog().yesno(
        "Ziro Games — Remove source",
        f"Remove this {label} source?\n\n{folder}",
    ):
        return
    purge = xbmcgui.Dialog().yesno(
        "Ziro Games — Library cleanup",
        "Also remove games imported from this source folder?\n\n"
        "Yes = hide those games from your library\n"
        "No = keep the games, only remove the source folder",
    )
    router.remove_source(source_id, purge_games=purge)
    refresh_home_platform_properties(router.db)
    xbmcgui.Dialog().notification("Ziro Games", "Source removed", xbmcgui.NOTIFICATION_INFO, 2500)
    xbmc.executebuiltin(
        f"ActivateWindow(Programs,plugin://plugin.program.ziro.games/?path=/sources,return)"
    )


def offer_artwork_fetch(router: Router) -> None:
    from resources.lib.metadata.screenscraper import credentials_configured

    if not credentials_configured():
        return
    if not ADDON.getSettingBool("metadata_fetch_on_scan"):
        return
    if not xbmcgui.Dialog().yesno(
        "Ziro Games",
        "Scan finished. Fetch missing box art from ScreenScraper now?\n\n"
        "Large libraries can take a while.",
    ):
        return
    run_artwork_fetch(router)


def run_artwork_fetch(router: Router) -> None:
    progress = xbmcgui.DialogProgress()
    progress.create("Ziro Games", "Fetching artwork from ScreenScraper...")

    def update(percent: int, label: str) -> bool:
        if progress.iscanceled():
            return False
        progress.update(percent, label[:80])
        return True

    try:
        result = router.fetch_missing_artwork(progress=update)
    finally:
        progress.close()

    summary = result.summary()
    if result.updated and not any(item.status == "api_error" for item in result.results):
        xbmcgui.Dialog().notification("Ziro Games", summary, xbmcgui.NOTIFICATION_INFO, 4000)
    else:
        xbmcgui.Dialog().ok("Ziro Games — Artwork", summary)
    refresh_home_platform_properties()
    xbmc.executebuiltin("Container.Refresh")


def show_artwork_refresh(game_id: int, router: Router) -> None:
    result = router.refresh_artwork(game_id)
    if result.status == "ok":
        xbmcgui.Dialog().notification("Ziro Games", f"Artwork updated for {result.title}", xbmcgui.NOTIFICATION_INFO, 2500)
    else:
        xbmcgui.Dialog().notification("Ziro Games", result.message or result.status, xbmcgui.NOTIFICATION_ERROR, 4000)


def main() -> None:
    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2].startswith("?") else {}
    path = params.get("path", "/home")
    if not path.startswith("/"):
        path = f"/{path}"
    db = GameDatabase()
    router = Router(db)
    refresh_home_platform_properties(db)

    try:
        if path == "/home":
            add_directory("Continue Playing", "/continue")
            add_directory("Recently Added", "/recent")
            add_directory("Favorites", "/favorites")
            add_directory("Platforms", "/platforms")
            add_directory("Genres", "/genres")
            add_directory("Sources", "/sources")
            add_action("Scan / Refresh Library", "/scan")
            add_action("Fetch Missing Artwork (ScreenScraper)", "/scrape")
            add_action("Settings", "/settings")
            xbmcplugin.setContent(HANDLE, "files")
            xbmcplugin.endOfDirectory(HANDLE)
        elif path == "/library":
            refresh_home_platform_properties(db)
            render_library_menu(router)
        elif path == "/all":
            render_game_list(router.all_games(), "No games yet")
        elif path == "/continue":
            render_game_list(router.continue_playing(), "Nothing in Continue Playing")
        elif path == "/recent":
            render_game_list(router.recently_added(), "No recently added games")
        elif path == "/favorites":
            render_game_list(router.favorites(), "No favorite games")
        elif path == "/platforms":
            for platform in router.platforms():
                count = int(platform.get("game_count") or 0)
                add_platform_directory(
                    platform,
                    f"/platform/{platform['id']}",
                    f"{count} games",
                )
            xbmcplugin.setContent(HANDLE, "games")
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
            add_action("Add Game Source...", "/sources/add")
            for source in router.sources():
                add_source_item(source)
            xbmcplugin.setContent(HANDLE, "files")
            xbmcplugin.endOfDirectory(HANDLE)
        elif path == "/sources/add":
            platform_id = params.get("platform_id") or pick_platform_id()
            if not platform_id:
                xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
                return
            platform = get_platform(platform_id)
            if not platform:
                raise ValueError(f"Unsupported platform: {platform_id}")
            selected = browse_for_source(platform.name)
            if selected:
                if not is_allowed_source_folder(selected):
                    xbmcgui.Dialog().ok(
                        "Ziro Games",
                        "That folder cannot be used as a game source.\n\n"
                        "Choose your ROM folder, not Kodi addons, dist, or skin files.",
                    )
                    xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
                    return
                router.add_source(platform_id, selected)
                xbmcgui.Dialog().notification(
                    "Ziro Games",
                    f"{platform.name} source added",
                    xbmcgui.NOTIFICATION_INFO,
                    2500,
                )
                if xbmcgui.Dialog().yesno("Ziro Games", "Source added. Scan now?"):
                    scan_in_background(offer_artwork=True)
                xbmc.executebuiltin("Container.Refresh")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/sources/remove":
            source_id = int(params["source_id"])
            confirm_remove_source(router, source_id)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/launch":
            game_id = params.get("game_id")
            if not game_id:
                raise ValueError("Missing game_id")
            xbmc.executebuiltin(f"RunScript(script.ziro.games.launcher,game_id={game_id})")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/info":
            game_id = params.get("game_id")
            if not game_id:
                raise ValueError("Missing game_id")
            show_game_info(int(game_id))
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/sync_home":
            from resources.lib.scanner import purge_junk_games

            purge_junk_games(db)
            refresh_home_platform_properties(db)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/favorite":
            router.toggle_favorite(int(params["game_id"]))
            xbmcgui.Dialog().notification("Ziro Games", "Favorite updated", xbmcgui.NOTIFICATION_INFO, 2000)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/refresh":
            game_id = int(params["game_id"])
            show_artwork_refresh(game_id, router)
            xbmc.executebuiltin("Container.Refresh")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/scan":
            scan_in_background(offer_artwork=ADDON.getSettingBool("metadata_fetch_on_scan"))
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/offer_artwork":
            offer_artwork_fetch(router)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/scrape":
            run_artwork_fetch(router)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/settings":
            open_addon_settings()
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        else:
            raise ValueError(f"Unknown route: {path}")
    except Exception as exc:
        xbmc.log(f"[Ziro Games] route failed path={path}: {exc}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Ziro Games", str(exc), xbmcgui.NOTIFICATION_ERROR, 5000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


if __name__ == "__main__":
    main()
