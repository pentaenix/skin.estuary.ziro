from __future__ import annotations

import xbmcgui

NAV_BACK_PROPERTY = "ziro_nav_back"


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


def set_browse_back(path: str) -> None:
    parent = parent_browse_path(path)
    try:
        window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    except RuntimeError:
        return
    if parent is None:
        clear_browse_back(window=window)
        return
    _back_path, label = parent
    window.setProperty("ZiroGames.BrowseBack", "1")
    window.setProperty("ZiroGames.BrowseBackLabel", label)


def clear_browse_back(*, window: xbmcgui.Window | None = None) -> None:
    if window is None:
        try:
            window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        except RuntimeError:
            return
    window.clearProperty("ZiroGames.BrowseBack")
    window.clearProperty("ZiroGames.BrowseBackLabel")
