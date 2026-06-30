from __future__ import annotations

BLOCKED_ROM_FRAGMENTS = (
    "ziro-addons",
    "skin.estuary.ziro",
    "/dist/",
    "\\dist\\",
    "plugin.program.ziro.games",
    "script.ziro.games.launcher",
    "service.ziro.games",
    "/addons/",
    "\\addons\\",
    "special://addons",
    "special://temp",
    "special://home",
)

BLOCKED_SOURCE_FRAGMENTS = BLOCKED_ROM_FRAGMENTS + (
    "/packages/",
    "\\packages\\",
)


def _normalize(path: str) -> str:
    return (path or "").replace("\\", "/").lower()


def is_library_rom_path(path: str) -> bool:
    if not path:
        return False
    norm = _normalize(path)
    if norm.endswith("/addon.xml") or norm.endswith("addon.xml"):
        return False
    if "plugin.program.ziro.games-" in norm and norm.endswith(".zip"):
        return False
    if norm.endswith("changelog.txt") or norm.endswith("readme.md"):
        return False
    return not any(fragment.lower() in norm for fragment in BLOCKED_ROM_FRAGMENTS)


def is_allowed_source_folder(path: str) -> bool:
    if not path or not path.strip():
        return False
    norm = _normalize(path)
    if any(fragment.lower() in norm for fragment in BLOCKED_SOURCE_FRAGMENTS):
        return False
    return True
