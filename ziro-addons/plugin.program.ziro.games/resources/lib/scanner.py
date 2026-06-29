from __future__ import annotations

import re
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcvfs

from .db import GameDatabase
from .platforms import LEGACY_SOURCE_SETTINGS, extensions_for, get_platform, iter_profile_defs, source_dict

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")

TITLE_JUNK = re.compile(r"\s*[\(\[].*?[\)\]]\s*")
SEPARATORS = re.compile(r"[._]+")


def normalize_folder(path: str) -> str:
    path = (path or "").strip().strip('"')
    if not path:
        return ""
    return path.rstrip("/\\")


def display_name(path: str) -> str:
    trimmed = path.rstrip("/\\")
    return trimmed.replace("\\", "/").split("/")[-1] or trimmed


def clean_title(path: str | Path) -> str:
    name = display_name(str(path))
    if "." in name:
        name = ".".join(name.split(".")[:-1]) or name
    title = SEPARATORS.sub(" ", name)
    title = TITLE_JUNK.sub(" ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or name


def sort_title(title: str) -> str:
    return re.sub(r"^(the|a|an)\s+", "", title.lower()).strip()


def vfs_join(folder: str, child: str) -> str:
    if folder.endswith(("/", "\\")):
        return folder + child
    if "\\" in folder and "/" not in folder:
        return folder + "\\" + child
    return folder + "/" + child


def iter_games(folder: str, extensions: list[str], recursive: bool = True):
    folder = normalize_folder(folder)
    if not folder or not xbmcvfs.exists(folder):
        return
    allowed = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions}
    try:
        dirs, files = xbmcvfs.listdir(folder)
    except Exception as exc:
        xbmc.log(f"[Ziro Games Scanner] cannot list folder {folder}: {exc}", xbmc.LOGWARNING)
        return
    for filename in files:
        suffix = Path(filename).suffix.lower()
        if suffix in allowed:
            yield vfs_join(folder, filename)
    if recursive:
        for dirname in dirs:
            child = vfs_join(folder, dirname)
            yield from iter_games(child, extensions, True) or []


def configure_defaults(db: GameDatabase) -> None:
    """Ensure emulator profiles exist and import legacy settings-folder sources if set."""
    for profile in iter_profile_defs():
        exe = ADDON.getSetting(profile["emulator_setting"])
        db.ensure_emulator_profile({
            "id": profile["id"],
            "name": profile["name"],
            "platform_id": profile["platform_id"],
            "executable_path": exe,
            "arguments_template": profile["arguments_template"],
            "working_directory": str(Path(exe).parent) if exe else "",
            "process_name": profile["process_name"],
            "exit_hotkey": "",
            "fullscreen": True,
            "return_focus_to_kodi": True,
        })

    for setting_key, platform_id in LEGACY_SOURCE_SETTINGS.items():
        legacy_source = normalize_folder(ADDON.getSetting(setting_key))
        if legacy_source:
            db.ensure_source({
                **source_dict(platform_id, legacy_source, label="Legacy settings source"),
            })


def source_for_platform(platform_id: str, folder_path: str) -> dict:
    folder = normalize_folder(folder_path)
    payload = source_dict(platform_id, folder, label=display_name(folder))
    return payload


def scan(db: GameDatabase) -> int:
    configure_defaults(db)
    count = 0
    sources = db.list_sources(enabled_only=True)
    for source in sources:
        platform_id = source["platform_id"]
        platform = get_platform(platform_id)
        if not platform:
            xbmc.log(f"[Ziro Games Scanner] unsupported source platform: {platform_id}", xbmc.LOGWARNING)
            continue
        folder = normalize_folder(source["folder_path"])
        if not folder or not xbmcvfs.exists(folder):
            xbmc.log(f"[Ziro Games Scanner] source missing for {platform_id}: {folder}", xbmc.LOGWARNING)
            continue
        exts = [f".{ext.strip().lstrip('.')}" for ext in (source.get("file_extensions") or "").split(",") if ext.strip()]
        default_exts = [f".{ext}" if not ext.startswith(".") else ext for ext in extensions_for(platform_id)]
        for rom in iter_games(folder, exts or default_exts, bool(source.get("recursive", 1))) or []:
            title = clean_title(rom)
            db.upsert_game({
                "title": title,
                "sort_title": sort_title(title),
                "platform_id": platform_id,
                "rom_path": str(rom),
                "emulator_profile_id": source.get("emulator_profile_id") or platform.profile_id,
                "source_id": source.get("id"),
                "description": f"Imported from {folder}",
            })
            count += 1
    return count
