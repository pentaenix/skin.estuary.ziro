from __future__ import annotations

import sys

import xbmcplugin

NAV_BACK_PROPERTY = "ziro_nav_back"


def _plugin_handle(handle: int | None = None) -> int | None:
    if handle is not None:
        return int(handle)
    try:
        return int(sys.argv[1])
    except (IndexError, TypeError, ValueError):
        return None


def parent_browse_path(path: str) -> tuple[str, str] | None:
    path = (path or "/library").rstrip("/") or "/library"
    if path in {"/library", "/home"}:
        return None
    if path.startswith("/platform/"):
        return "/platforms", "Back to Platforms"
    if path.startswith("/genre/"):
        return "/genres", "Back to Genres"
    if path == "/platforms":
        return "/library", "Back to Games Library"
    if path == "/genres":
        return "/library", "Back to Games Library"
    if path in {"/continue", "/recent", "/favorites", "/all", "/sources"}:
        return "/library", "Back to Games Library"
    return "/library", "Back to Games Library"


def set_browse_back(path: str, handle: int | None = None) -> None:
    resolved = _plugin_handle(handle)
    if resolved is None:
        return
    parent = parent_browse_path(path)
    if parent is None:
        clear_browse_back(resolved)
        return
    _back_path, label = parent
    xbmcplugin.setProperty(resolved, "ZiroGames.BrowseBack", "1")
    xbmcplugin.setProperty(resolved, "ZiroGames.BrowseBackLabel", label)


def clear_browse_back(handle: int | None = None) -> None:
    resolved = _plugin_handle(handle)
    if resolved is None:
        return
    xbmcplugin.setProperty(resolved, "ZiroGames.BrowseBack", "")
    xbmcplugin.setProperty(resolved, "ZiroGames.BrowseBackLabel", "")


def set_launch_hub(handle: int | None = None) -> None:
    resolved = _plugin_handle(handle)
    if resolved is None:
        return
    xbmcplugin.setProperty(resolved, "ZiroGames.LaunchHub", "1")


def clear_launch_hub(handle: int | None = None) -> None:
    resolved = _plugin_handle(handle)
    if resolved is None:
        return
    xbmcplugin.setProperty(resolved, "ZiroGames.LaunchHub", "")
