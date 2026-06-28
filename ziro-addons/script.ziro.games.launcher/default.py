from __future__ import annotations

import json
import os
import shlex
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import xbmc
import xbmcgui
import xbmcvfs

ADDON_DATA = Path(xbmcvfs.translatePath("special://profile/addon_data/plugin.program.ziro.games"))
DB_PATH = ADDON_DATA / "games.db"
SESSION_PATH = ADDON_DATA / "session.json"


def parse_args() -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in sys.argv[1:]:
        if "=" in raw:
            key, value = raw.split("=", 1)
            result[key] = value
    return result


def get_launch_data(game_id: int) -> tuple[dict, dict]:
    if game_id < 0:
        raise RuntimeError("Mock games cannot launch. Scan your real folders first.")
    if not DB_PATH.exists():
        raise RuntimeError("Ziro Games database does not exist yet. Run a scan first.")
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


def launch(game_id: int) -> None:
    game, profile = get_launch_data(game_id)
    executable = Path(profile["executable_path"])
    rom_path = Path(game["rom_path"])
    if not executable.exists():
        raise RuntimeError(f"Emulator executable missing: {executable}")
    if not rom_path.exists():
        raise RuntimeError(f"ROM path missing: {rom_path}")

    args_template = profile["arguments_template"] or '"{rom_path}"'
    args = args_template.format(rom_path=str(rom_path), executable_path=str(executable))
    cwd = profile.get("working_directory") or str(executable.parent)

    if os.name == "nt":
        # On Windows, avoid pre-splitting quoted paths. Let CreateProcess/cmd parse the command line.
        command = subprocess.list2cmdline([str(executable)]) + " " + args
        xbmc.log(f"[Ziro Games Launcher] launch game={game['title']} command={command} cwd={cwd}", xbmc.LOGINFO)
        proc = subprocess.Popen(command, cwd=cwd, shell=True)
    else:
        command = [str(executable)] + shlex.split(args)
        xbmc.log(f"[Ziro Games Launcher] launch game={game['title']} command={command} cwd={cwd}", xbmc.LOGINFO)
        proc = subprocess.Popen(command, cwd=cwd)
    ADDON_DATA.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps({
        "game_id": game_id,
        "title": game["title"],
        "pid": proc.pid,
        "process_name": profile.get("process_name") or executable.name,
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
        xbmcgui.Dialog().notification("Ziro Games", str(exc), xbmcgui.NOTIFICATION_ERROR, 6000)


if __name__ == "__main__":
    main()
