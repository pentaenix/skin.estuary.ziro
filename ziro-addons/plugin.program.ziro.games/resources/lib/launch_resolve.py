from __future__ import annotations

import os

import xbmcaddon
import xbmcvfs

from .platforms import get_platform

PLUGIN_ID = "plugin.program.ziro.games"


def _exists(path: str) -> bool:
    if not path or not str(path).strip():
        return False
    try:
        return bool(xbmcvfs.exists(path))
    except Exception:
        return False


def _path_candidates(path: str) -> list[str]:
    raw = (path or "").strip()
    if not raw:
        return []
    translated = xbmcvfs.translatePath(raw)
    seen: set[str] = set()
    result: list[str] = []
    for item in (raw, translated):
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def normalize_launch_path(path: str) -> str:
    if not path:
        return ""
    if os.name == "nt":
        return path.replace("/", "\\")
    return path


def resolve_executable_path(profile: dict, platform_id: str) -> str:
    addon = xbmcaddon.Addon(PLUGIN_ID)
    platform = get_platform(platform_id)
    candidates: list[str] = []
    db_exe = (profile.get("executable_path") or "").strip()
    if db_exe:
        candidates.extend(_path_candidates(db_exe))
    if platform:
        setting_exe = (addon.getSetting(platform.emulator_setting) or "").strip()
        if setting_exe:
            candidates.extend(_path_candidates(setting_exe))
    for candidate in candidates:
        if _exists(candidate):
            return normalize_launch_path(candidate)
    fallback = db_exe or ((addon.getSetting(platform.emulator_setting) or "").strip() if platform else "")
    return normalize_launch_path(fallback)


def resolve_rom_path(rom_path: str) -> str:
    for candidate in _path_candidates(rom_path):
        if _exists(candidate):
            return normalize_launch_path(candidate)
    return normalize_launch_path((rom_path or "").strip())
