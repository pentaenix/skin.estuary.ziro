from __future__ import annotations

# ScreenScraper numeric system IDs (see screenscraper.fr systemelist.php).
SCREENSCRAPER_SYSTEM_IDS: dict[str, int] = {
    "nes": 3,
    "snes": 4,
    "n64": 9,
    "gb": 9,
    "gbc": 10,
    "gba": 12,
    "nds": 15,
    "3ds": 17,
    "gamecube": 13,
    "wii": 38,
    "wiiu": 47,
    "switch": 225,
    "sms": 2,
    "genesis": 1,
    "segacd": 20,
    "saturn": 22,
    "dreamcast": 23,
    "ps1": 7,
    "ps2": 8,
    "ps3": 71,
    "psp": 14,
    "psvita": 39,
    "ps4": 111,
    "xbox": 32,
    "xbox360": 31,
    "xboxone": 48,
    "xboxseries": 48,
}

# Tall case art (movie-style rows). Handhelds / cartridges use square box rows.
POSTER_COVER_PLATFORMS = frozenset({
    "wii",
    "wiiu",
    "gamecube",
    "switch",
    "ps1",
    "ps2",
    "ps3",
    "ps4",
    "xbox",
    "xbox360",
    "xboxone",
    "xboxseries",
    "dreamcast",
    "saturn",
    "segacd",
    "3ds",
})


def screenscraper_system_id(platform_id: str) -> int | None:
    return SCREENSCRAPER_SYSTEM_IDS.get(platform_id)


def cover_aspect(platform_id: str) -> str:
    return "poster" if platform_id in POSTER_COVER_PLATFORMS else "box"
