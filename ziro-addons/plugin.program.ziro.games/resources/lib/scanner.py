from __future__ import annotations

import re
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcvfs

from .db import GameDatabase

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")

SYSTEMS = {
    "gamecube": {
        "source_setting": "source_gamecube",
        "profile": "dolphin_gamecube",
        "extensions": [".rvz", ".iso", ".gcm"],
        "emulator_setting": "emulator_dolphin",
        "emulator_name": "Dolphin GameCube",
        "args": '-b -e "{rom_path}"',
        "process": "Dolphin.exe",
    },
    "wii": {
        "source_setting": "source_wii",
        "profile": "dolphin_wii",
        "extensions": [".rvz", ".iso", ".wbfs", ".wad"],
        "emulator_setting": "emulator_dolphin",
        "emulator_name": "Dolphin Wii",
        "args": '-b -e "{rom_path}"',
        "process": "Dolphin.exe",
    },
    "gba": {
        "source_setting": "source_gba",
        "profile": "mgba_gba",
        "extensions": [".gba", ".gb", ".gbc", ".zip"],
        "emulator_setting": "emulator_mgba",
        "emulator_name": "mGBA",
        "args": '-f "{rom_path}"',
        "process": "mGBA.exe",
    },
}

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
        xbmc.log(f"[Ziro Games] cannot list folder {folder}: {exc}", xbmc.LOGWARNING)
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
    for platform_id, cfg in SYSTEMS.items():
        exe = ADDON.getSetting(cfg["emulator_setting"])
        db.ensure_emulator_profile({
            "id": cfg["profile"],
            "name": cfg["emulator_name"],
            "platform_id": platform_id,
            "executable_path": exe,
            "arguments_template": cfg["args"],
            "working_directory": str(Path(exe).parent) if exe else "",
            "process_name": cfg["process"],
            "exit_hotkey": "",
            "fullscreen": True,
            "return_focus_to_kodi": True,
        })
        legacy_source = normalize_folder(ADDON.getSetting(cfg["source_setting"]))
        if legacy_source:
            db.ensure_source({
                "platform_id": platform_id,
                "folder_path": legacy_source,
                "recursive": True,
                "file_extensions": [ext.lstrip(".") for ext in cfg["extensions"]],
                "emulator_profile_id": cfg["profile"],
                "label": "Legacy settings source",
            })


def source_for_platform(platform_id: str, folder_path: str) -> dict:
    cfg = SYSTEMS[platform_id]
    return {
        "platform_id": platform_id,
        "folder_path": normalize_folder(folder_path),
        "recursive": True,
        "file_extensions": [ext.lstrip(".") for ext in cfg["extensions"]],
        "emulator_profile_id": cfg["profile"],
        "label": display_name(folder_path),
    }


def scan(db: GameDatabase) -> int:
    configure_defaults(db)
    count = 0
    sources = db.list_sources(enabled_only=True)
    for source in sources:
        platform_id = source["platform_id"]
        cfg = SYSTEMS.get(platform_id)
        if not cfg:
            xbmc.log(f"[Ziro Games] unsupported source platform: {platform_id}", xbmc.LOGWARNING)
            continue
        folder = normalize_folder(source["folder_path"])
        if not folder or not xbmcvfs.exists(folder):
            xbmc.log(f"[Ziro Games] source missing for {platform_id}: {folder}", xbmc.LOGWARNING)
            continue
        exts = [f".{ext.strip().lstrip('.')}" for ext in (source.get("file_extensions") or "").split(",") if ext.strip()]
        for rom in iter_games(folder, exts or cfg["extensions"], bool(source.get("recursive", 1))) or []:
            title = clean_title(rom)
            db.upsert_game({
                "title": title,
                "sort_title": sort_title(title),
                "platform_id": platform_id,
                "rom_path": str(rom),
                "emulator_profile_id": source.get("emulator_profile_id") or cfg["profile"],
                "source_id": source.get("id"),
                "description": f"Imported from {folder}",
            })
            count += 1
    return count
