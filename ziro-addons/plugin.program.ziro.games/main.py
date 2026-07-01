from __future__ import annotations

import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.app_title import app_title
from resources.lib.db import GameDatabase
from resources.lib.game_info import show_game_info
from resources.lib.home_state import refresh_home_platform_properties, refresh_home_properties
from resources.lib.metadata.platform_art import choose_platform_art, get_platform_art_path
from resources.lib.paths_filter import is_allowed_source_folder
from resources.lib.platforms import get_platform, platform_choices
from resources.lib.routes import Router
from resources.lib.scan_jobs import scan_in_background

from resources.lib.metadata.providers import game_artwork_provider

ADDON = xbmcaddon.Addon()
APP_NAME = app_title()
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
    item.addContextMenuItems([
        (
            "Choose console artwork (SteamGridDB)",
            f"RunPlugin({plugin_url('/platforms/art/pick', platform_id=platform_id)})",
        ),
    ])
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
        ("Choose artwork", f"RunPlugin({plugin_url('/choose_art', game_id=str(game['id']))})"),
    ])
    xbmcplugin.addDirectoryItem(HANDLE, _game_item_url(int(game["id"])), item, False)


def render_library_menu(router: Router) -> None:
    has_games = bool(router.all_games(limit=1))
    if not has_games:
        add_action("Add Game Source", "/sources/add")
        add_action("Scan / Refresh Library", "/scan")
        xbmcplugin.setContent(HANDLE, "games")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    if router.continue_playing():
        add_library_entry("Continue Playing", "/continue", "Games you have launched recently")
    if router.recently_added(limit=1):
        add_library_entry("Recently Added", "/recent", "Newest games in your library")
    if router.favorites():
        add_library_entry("Favorites", "/favorites", "Games you marked as favorites")
    add_library_entry("Platforms", "/platforms", "Browse by console")
    add_library_entry("Genres", "/genres", "Browse by genre")
    add_library_entry("All Games", "/all", "Full game list")
    add_action("Scan / Refresh Library", "/scan")
    add_action("Refresh All Artwork", "/refresh_artwork")
    add_library_entry("Sources", "/sources", "ROM folders and platforms")
    add_action("Settings", "/settings")
    xbmcplugin.setContent(HANDLE, "games")
    xbmcplugin.endOfDirectory(HANDLE)


def render_game_list(games: list[dict]) -> None:
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
        xbmcgui.Dialog().notification(APP_NAME, headline, xbmcgui.NOTIFICATION_INFO, 4000)
        return
    xbmc.log(f"[Games Scanner] {summary}", xbmc.LOGWARNING)
    xbmcgui.Dialog().notification(APP_NAME, headline, xbmcgui.NOTIFICATION_WARNING, 5000)


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
        xbmcgui.Dialog().notification(APP_NAME, "Source not found", xbmcgui.NOTIFICATION_ERROR, 3000)
        return
    label = source.get("platform_name") or source["platform_id"]
    folder = source.get("folder_path") or ""
    if not xbmcgui.Dialog().yesno(
        "Remove source",
        f"Remove this {label} source?\n\n{folder}",
    ):
        return
    purge = xbmcgui.Dialog().yesno(
        "Library cleanup",
        "Also remove games imported from this source folder?\n\n"
        "Yes = hide those games from your library\n"
        "No = keep the games, only remove the source folder",
    )
    router.remove_source(source_id, purge_games=purge)
    from resources.lib.scanner import purge_junk_games

    purge_junk_games(router.db)
    router.db.clear_play_state_for_hidden_games()
    refresh_home_platform_properties(router.db)
    xbmcgui.Dialog().notification(APP_NAME, "Source removed", xbmcgui.NOTIFICATION_INFO, 2500)
    xbmc.executebuiltin(
        f"ActivateWindow(Programs,plugin://plugin.program.ziro.games/?path=/sources,return)"
    )


def offer_artwork_fetch(router: Router) -> None:
    from resources.lib.metadata.providers import PROVIDER_SKRAPER, PROVIDER_STEAMGRIDDB, steamgriddb_api_key
    from resources.lib.metadata.screenscraper import credentials_configured
    from resources.lib.metadata.steamgriddb import validate_api_key

    provider = game_artwork_provider()
    if provider == PROVIDER_SKRAPER:
        label = "Skraper / local files"
    elif provider == PROVIDER_STEAMGRIDDB:
        if not steamgriddb_api_key() or not validate_api_key(steamgriddb_api_key()):
            return
        label = "SteamGridDB"
    else:
        if not credentials_configured():
            return
        label = "ScreenScraper"
    if not ADDON.getSettingBool("metadata_fetch_on_scan"):
        return
    prompt = (
        f"Scan finished. Import missing metadata from {label} now?\n\n"
        "Uses gamelist.xml and media folders next to your ROMs."
        if provider == PROVIDER_SKRAPER
        else f"Scan finished. Fetch missing box art from {label} now?\n\nLarge libraries can take a while."
    )
    if not xbmcgui.Dialog().yesno(APP_NAME, prompt):
        return
    run_artwork_fetch(router)


def _provider_label(provider: str) -> str:
    from resources.lib.metadata.providers import PROVIDER_SKRAPER, PROVIDER_STEAMGRIDDB

    if provider == PROVIDER_STEAMGRIDDB:
        return "SteamGridDB"
    if provider == PROVIDER_SKRAPER:
        return "Skraper / local files"
    return "ScreenScraper"


def run_artwork_fetch(router: Router, *, refresh_all: bool = False) -> None:
    provider = game_artwork_provider()
    label = _provider_label(provider)
    heading = "Refresh all artwork" if refresh_all else "Fetch missing artwork"
    progress = xbmcgui.DialogProgress()
    progress.create(APP_NAME, f"{heading} from {label}...")

    def update(percent: int, item_label: str) -> bool:
        if progress.iscanceled():
            return False
        progress.update(percent, item_label[:80])
        return True

    try:
        if refresh_all:
            result = router.refresh_all_artwork(progress=update)
        else:
            result = router.fetch_missing_artwork(progress=update)
    finally:
        progress.close()

    summary = result.summary()
    if result.updated and not any(item.status == "api_error" for item in result.results):
        xbmcgui.Dialog().notification(APP_NAME, summary.splitlines()[0], xbmcgui.NOTIFICATION_INFO, 4000)
    else:
        xbmcgui.Dialog().ok("Artwork", summary)
    refresh_home_properties()
    xbmc.executebuiltin("Container.Refresh")


def show_artwork_refresh(game_id: int, router: Router) -> None:
    result = router.refresh_artwork(game_id)
    if result.status == "ok":
        xbmcgui.Dialog().notification(APP_NAME, f"Artwork updated for {result.title}", xbmcgui.NOTIFICATION_INFO, 2500)
    else:
        xbmcgui.Dialog().notification(APP_NAME, result.message or result.status, xbmcgui.NOTIFICATION_ERROR, 4000)


def main() -> None:
    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2].startswith("?") else {}
    path = params.get("path", "/home")
    if not path.startswith("/"):
        path = f"/{path}"
    db = GameDatabase()
    router = Router(db)
    refresh_home_platform_properties(db)

    try:
        if path in {"/home", "/library"}:
            refresh_home_properties(db)
            render_library_menu(router)
        elif path == "/all":
            render_game_list(router.all_games())
        elif path == "/continue":
            render_game_list(router.continue_playing())
        elif path == "/recent":
            render_game_list(router.recently_added())
        elif path == "/favorites":
            render_game_list(router.favorites())
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
        elif path == "/platforms/icons":
            for platform in router.platforms():
                add_action(
                    f"{platform['name']} — choose icon",
                    f"/platforms/art/pick?platform_id={platform['id']}",
                )
            xbmcplugin.setContent(HANDLE, "files")
            xbmcplugin.endOfDirectory(HANDLE)
        elif path == "/platforms/art/pick":
            platform_id = params.get("platform_id") or ""
            if platform_id:
                choose_platform_art(platform_id)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
            xbmc.executebuiltin("Container.Refresh")
        elif path.startswith("/platform/"):
            platform_id = path.rsplit("/", 1)[-1]
            render_game_list(router.by_platform(platform_id))
        elif path == "/genres":
            for genre in router.genres():
                add_directory(genre["name"], f"/genre/{genre['id']}")
            xbmcplugin.endOfDirectory(HANDLE)
        elif path.startswith("/genre/"):
            genre_id = path.rsplit("/", 1)[-1]
            render_game_list(router.by_genre(genre_id))
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
                        APP_NAME,
                        "That folder cannot be used as a game source.\n\n"
                        "Choose your ROM folder, not Kodi addons, dist, or skin files.",
                    )
                    xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
                    return
                router.add_source(platform_id, selected)
                xbmcgui.Dialog().notification(
                    APP_NAME,
                    f"{platform.name} source added",
                    xbmcgui.NOTIFICATION_INFO,
                    2500,
                )
                if xbmcgui.Dialog().yesno(APP_NAME, "Source added. Scan now?"):
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
            db.clear_play_state_for_hidden_games()
            refresh_home_properties(db)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/choose_art":
            from resources.lib.metadata.art_picker import choose_game_art

            choose_game_art(int(params["game_id"]))
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/favorite":
            router.toggle_favorite(int(params["game_id"]))
            xbmcgui.Dialog().notification(APP_NAME, "Favorite updated", xbmcgui.NOTIFICATION_INFO, 2000)
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
            run_artwork_fetch(router, refresh_all=False)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/refresh_artwork":
            from resources.lib.metadata.providers import PROVIDER_SKRAPER, PROVIDER_STEAMGRIDDB, steamgriddb_api_key
            from resources.lib.metadata.screenscraper import credentials_configured
            from resources.lib.metadata.steamgriddb import validate_api_key

            provider = game_artwork_provider()
            if provider == PROVIDER_SKRAPER:
                label = "Skraper / local files"
            elif provider == PROVIDER_STEAMGRIDDB:
                if not steamgriddb_api_key() or not validate_api_key(steamgriddb_api_key()):
                    xbmcgui.Dialog().ok(APP_NAME, "Set a valid SteamGridDB API key in settings first.")
                    xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
                    return
                label = "SteamGridDB"
            elif not credentials_configured():
                xbmcgui.Dialog().ok(APP_NAME, "Set ScreenScraper credentials in settings first.")
                xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
                return
            else:
                label = "ScreenScraper"
            if provider == PROVIDER_SKRAPER:
                prompt = (
                    "Re-import metadata for every game from gamelist.xml and local media folders?\n\n"
                    "Run Skraper on your PC first, then point your ROM source folder at the scraped output."
                )
            else:
                prompt = (
                    f"Refresh artwork for every game in your library from {label}?\n\n"
                    "Each game uses its platform when matching on ScreenScraper.\n"
                    "Large libraries can take a while."
                )
            if not xbmcgui.Dialog().yesno(APP_NAME, prompt):
                xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
                return
            run_artwork_fetch(router, refresh_all=True)
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        elif path == "/settings":
            open_addon_settings()
            xbmcplugin.endOfDirectory(HANDLE, succeeded=True, updateListing=False)
        else:
            raise ValueError(f"Unknown route: {path}")
    except Exception as exc:
        xbmc.log(f"[Games] route failed path={path}: {exc}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(APP_NAME, str(exc), xbmcgui.NOTIFICATION_ERROR, 5000)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


if __name__ == "__main__":
    main()
