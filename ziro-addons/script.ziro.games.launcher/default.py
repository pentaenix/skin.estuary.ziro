from __future__ import annotations

import json
import os
import shlex
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

PLUGIN_ID = "plugin.program.ziro.games"

# Shared platform catalog lives in the plugin add-on.
sys.path.insert(0, xbmcvfs.translatePath(f"special://addons/{PLUGIN_ID}"))
from resources.lib.platforms import get_platform, resolve_core_path  # noqa: E402

ADDON_DATA = Path(xbmcvfs.translatePath("special://profile/addon_data/plugin.program.ziro.games"))
DB_PATH = ADDON_DATA / "games.db"
SESSION_PATH = ADDON_DATA / "session.json"


def _path_exists(path: str) -> bool:
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


def _normalize_launch_path(path: str) -> str:
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
        if _path_exists(candidate):
            return _normalize_launch_path(candidate)
    fallback = db_exe or ((addon.getSetting(platform.emulator_setting) or "").strip() if platform else "")
    return _normalize_launch_path(fallback)


def resolve_rom_path(rom_path: str) -> str:
    for candidate in _path_candidates(rom_path):
        if _path_exists(candidate):
            return _normalize_launch_path(candidate)
    return _normalize_launch_path((rom_path or "").strip())


def parse_args() -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in sys.argv[1:]:
        if "=" in raw:
            key, value = raw.split("=", 1)
            result[key] = value
    return result


def get_launch_data(game_id: int) -> tuple[dict, dict]:
    if not DB_PATH.exists():
        raise RuntimeError("Games database does not exist yet. Run a scan first.")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    with conn:
        game = conn.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
        if not game:
            raise RuntimeError(f"Game not found: {game_id}")
        profile = conn.execute("SELECT * FROM emulator_profiles WHERE id=?", (game["emulator_profile_id"],)).fetchone()
        if not profile:
            raise RuntimeError(f"Emulator profile not found: {game['emulator_profile_id']}")
        return dict(game), dict(profile)


def process_running(process_name: str) -> bool:
    if not process_name:
        return False
    if os.name == "nt":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return process_name.lower() in out.lower()
        except Exception:
            return False
    return False


def verify_process_started(proc: subprocess.Popen, process_name: str, executable_path: str) -> None:
    names = [name for name in {process_name, Path(executable_path).name} if name]
    time.sleep(1.0)
    if os.name == "nt":
        if any(process_running(name) for name in names):
            return
        code = proc.poll()
        if code is not None:
            raise RuntimeError(f"Emulator exited immediately (code {code}). Check Dolphin path and ROM.")
        label = names[0] if names else "emulator"
        raise RuntimeError(f"Emulator did not start ({label}). Check Games settings and kodi.log.")
    if proc.poll() is not None:
        raise RuntimeError(f"Emulator exited immediately (code {proc.returncode})")


def launch(game_id: int) -> None:
    game, profile = get_launch_data(game_id)
    executable_path = resolve_executable_path(profile, game["platform_id"])
    rom_path = resolve_rom_path(game["rom_path"])
    if not executable_path:
        platform = get_platform(game["platform_id"])
        label = platform.emulator_name if platform else "Emulator"
        raise RuntimeError(f"{label} path not configured. Set it in Games settings, then scan.")
    if not xbmcvfs.exists(executable_path):
        raise RuntimeError(f"Emulator executable missing: {executable_path}")
    if not xbmcvfs.exists(rom_path):
        raise RuntimeError(f"Game file not found: {rom_path}")

    args_template = profile["arguments_template"] or '"{rom_path}"'
    platform = get_platform(game["platform_id"])
    core_path = resolve_core_path(executable_path, platform.retroarch_core if platform else "")
    args = args_template.format(
        rom_path=rom_path,
        rom_dir=str(Path(rom_path).parent),
        rom_file=Path(rom_path).name,
        rom_name=Path(rom_path).stem,
        executable_path=executable_path,
        core_path=core_path,
    )
    cwd = profile.get("working_directory") or str(Path(executable_path).parent)
    if cwd and not xbmcvfs.exists(cwd):
        cwd = str(Path(executable_path).parent)
    process_name = profile.get("process_name") or Path(executable_path).name

    if os.name == "nt":
        command = subprocess.list2cmdline([executable_path]) + " " + args
        xbmc.log(f"[Ziro Games Launcher] launch game={game['title']} command={command} cwd={cwd}", xbmc.LOGINFO)
        proc = subprocess.Popen(command, cwd=cwd, shell=True)
    else:
        command = [executable_path] + shlex.split(args)
        xbmc.log(f"[Ziro Games Launcher] launch game={game['title']} command={command} cwd={cwd}", xbmc.LOGINFO)
        proc = subprocess.Popen(command, cwd=cwd)

    verify_process_started(proc, process_name, executable_path)

    ADDON_DATA.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps({
        "game_id": game_id,
        "title": game["title"],
        "pid": proc.pid,
        "process_name": process_name,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "return_focus_to_kodi": bool(profile.get("return_focus_to_kodi", 1)),
    }, indent=2), encoding="utf-8")

    conn = sqlite3.connect(str(DB_PATH))
    with conn:
        conn.execute("UPDATE games SET last_played=CURRENT_TIMESTAMP, play_count=play_count+1 WHERE id=?", (game_id,))


def main() -> None:
    args = parse_args()
    try:
        launch(int(args["game_id"]))
    except Exception as exc:
        xbmc.log(f"[Ziro Games Launcher] failed: {exc}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Games", str(exc), xbmcgui.NOTIFICATION_ERROR, 6000)


if __name__ == "__main__":
    main()
