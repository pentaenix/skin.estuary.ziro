from __future__ import annotations

import re
from pathlib import Path

import xbmc
import xbmcaddon

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


def clean_title(path: Path) -> str:
    title = path.stem
    title = SEPARATORS.sub(" ", title)
    title = TITLE_JUNK.sub(" ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or path.stem


def sort_title(title: str) -> str:
    return re.sub(r"^(the|a|an)\s+", "", title.lower()).strip()


def iter_games(folder: Path, extensions: list[str], recursive: bool = True):
    if not folder.exists():
        return
    pattern = "**/*" if recursive else "*"
    allowed = {ext.lower() for ext in extensions}
    for path in folder.glob(pattern):
        if path.is_file() and path.suffix.lower() in allowed:
            yield path


def configure_defaults(db: GameDatabase) -> None:
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
        source = ADDON.getSetting(cfg["source_setting"])
        if source:
            db.ensure_source({
                "platform_id": platform_id,
                "folder_path": source,
                "recursive": True,
                "file_extensions": [ext.lstrip(".") for ext in cfg["extensions"]],
                "emulator_profile_id": cfg["profile"],
            })


def scan(db: GameDatabase) -> int:
    configure_defaults(db)
    count = 0
    for platform_id, cfg in SYSTEMS.items():
        folder = Path(ADDON.getSetting(cfg["source_setting"]))
        if not folder.exists():
            xbmc.log(f"[Ziro Games] source missing for {platform_id}: {folder}", xbmc.LOGWARNING)
            continue
        for rom in iter_games(folder, cfg["extensions"], True) or []:
            title = clean_title(rom)
            db.upsert_game({
                "title": title,
                "sort_title": sort_title(title),
                "platform_id": platform_id,
                "rom_path": str(rom),
                "emulator_profile_id": cfg["profile"],
                "description": f"Imported from {folder}",
            })
            count += 1
    return count
