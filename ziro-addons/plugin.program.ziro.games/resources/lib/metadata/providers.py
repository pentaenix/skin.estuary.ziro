from __future__ import annotations

import xbmcaddon

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")

PROVIDER_SCREENSCRAPER = "screenscraper"
PROVIDER_STEAMGRIDDB = "steamgriddb"
PROVIDER_SKRAPER = "skraper"

PLATFORM_ART_BADGE = "badge"
PLATFORM_ART_SCREENSCRAPER = "screenscraper"
PLATFORM_ART_STEAMGRIDDB = "steamgriddb"


def game_artwork_provider() -> str:
    value = (ADDON.getSetting("game_artwork_provider") or PROVIDER_SCREENSCRAPER).strip().lower()
    if value in {PROVIDER_SCREENSCRAPER, PROVIDER_STEAMGRIDDB, PROVIDER_SKRAPER}:
        return value
    return PROVIDER_SCREENSCRAPER


def platform_art_provider() -> str:
    value = (ADDON.getSetting("platform_art_provider") or PLATFORM_ART_STEAMGRIDDB).strip().lower()
    if value in {PLATFORM_ART_BADGE, PLATFORM_ART_SCREENSCRAPER, PLATFORM_ART_STEAMGRIDDB}:
        return value
    return PLATFORM_ART_STEAMGRIDDB


def artwork_show_picker() -> bool:
    return ADDON.getSettingBool("metadata_show_picker")


def steamgriddb_api_key() -> str:
    from .http_client import normalize_api_key

    return normalize_api_key(ADDON.getSetting("steamgriddb_api_key") or "")
