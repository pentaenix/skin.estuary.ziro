from __future__ import annotations

import re

BLOCKED_ROM_FRAGMENTS = (
    "ziro-addons",
    "skin.estuary.ziro",
    "skin.estuary",
    "estuary.ziro",
    "/dist/",
    "\\dist\\",
    "plugin.program.ziro",
    "plugin.program.",
    "script.ziro.games",
    "service.ziro.games",
    "/addons/",
    "\\addons\\",
    "/roaming/kodi/addons/",
    "special://addons",
    "special://temp",
    "special://home",
    "/packages/",
    "\\packages\\",
)

BLOCKED_SOURCE_FRAGMENTS = BLOCKED_ROM_FRAGMENTS + (
    "/github/",
    "/documents/",
    "appdata/roaming/kodi",
)

ADDON_ARCHIVE_RE = re.compile(
    r"(plugin|script|service|skin)\.[a-z0-9_.-]+\.(zip|rar|7z)$",
    re.IGNORECASE,
)


def _normalize(path: str) -> str:
    return (path or "").replace("\\", "/").lower()


def _basename(path: str) -> str:
    norm = _normalize(path)
    return norm.rsplit("/", 1)[-1]


def is_library_rom_path(path: str) -> bool:
    if not path or not str(path).strip():
        return False
    norm = _normalize(path)
    base = _basename(path)

    if norm.endswith("/addon.xml") or base == "addon.xml":
        return False
    if base in {"changelog.txt", "readme.md", "license.txt", "settings.xml"}:
        return False
    if ADDON_ARCHIVE_RE.search(base):
        return False
    if "plugin.program.ziro.games-" in base and base.endswith(".zip"):
        return False
    if base.endswith((".zip", ".rar", ".7z")) and any(
        token in norm for token in ("ziro", "estuary", "/addons/", "github/personal/kodi", "/dist/")
    ):
        return False
    if "ziro" in base and base.endswith((".zip", ".rar", ".7z", ".py", ".xml")):
        return False
    return not any(fragment.lower() in norm for fragment in BLOCKED_ROM_FRAGMENTS)


def is_allowed_source_folder(path: str) -> bool:
    if not path or not path.strip():
        return False
    norm = _normalize(path)
    return not any(fragment.lower() in norm for fragment in BLOCKED_SOURCE_FRAGMENTS)
