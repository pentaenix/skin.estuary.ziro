from __future__ import annotations

import xbmcaddon

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")


def app_title() -> str:
    return ADDON.getAddonInfo("name") or "Games"
