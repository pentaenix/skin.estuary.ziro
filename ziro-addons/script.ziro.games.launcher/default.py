from __future__ import annotations

import json
import os
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
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RETURN_PATH = "plugin://plugin.program.ziro.games/?path=/library"

ADDON_DATA = Path(xbmcvfs.translatePath("special://profile/addon_data/plugin.program.ziro.games"))
SESSION_PATH = ADDON_DATA / "session.json"


def parse_args() -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in sys.argv[1:]:
        if "=" in raw:
            key, value = raw.split("=", 1)
            result[key] = value
    return result


def _path_exists(path: str) -> bool:
    if not path or not str(path).strip():
        return False
    try:
        return bool(xbmcvfs.exists(path))
    except Exception:
        return False


def _resolve_executable(setting_key: str) -> str:
    addon = xbmcaddon.Addon(PLUGIN_ID)
    raw = (addon.getSetting(setting_key) or "").strip()
    if not raw:
        return ""
    for candidate in (raw, xbmcvfs.translatePath(raw)):
        if candidate and _path_exists(candidate):
            return candidate.replace("/", "\\") if os.name == "nt" else candidate
    return raw.replace("/", "\\") if os.name == "nt" else raw


def process_running(process_name: str) -> bool:
    if not process_name or os.name != "nt":
        return False
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
        )
        return process_name.lower() in out.lower()
    except Exception:
        return False


def start_process(command: list[str], cwd: str) -> subprocess.Popen:
    popen_kwargs: dict = {"cwd": cwd}
    if os.name == "nt":
        popen_kwargs["creationflags"] = _CREATE_NO_WINDOW
    return subprocess.Popen(command, **popen_kwargs)


def verify_process_started(proc: subprocess.Popen, process_name: str) -> None:
    deadline = time.time() + 15.0
    while time.time() < deadline:
        if process_running(process_name):
            return
        if os.name != "nt" and proc.poll() is not None:
            raise RuntimeError(f"EmulationStation exited immediately (code {proc.returncode})")
        time.sleep(0.25)
    code = proc.poll()
    if code is not None:
        raise RuntimeError(f"EmulationStation exited immediately (code {code}). Check the executable path.")
    raise RuntimeError(f"EmulationStation did not start ({process_name}). Check Games settings and kodi.log.")


def launch_emulationstation() -> None:
    executable_path = _resolve_executable("emulator_emulationstation")
    if not executable_path:
        raise RuntimeError("EmulationStation path not configured. Set it in Games settings.")
    if not _path_exists(executable_path):
        raise RuntimeError(f"EmulationStation executable missing: {executable_path}")

    cwd = str(Path(executable_path).parent)
    process_name = Path(executable_path).name
    command = [executable_path]
    xbmc.log(f"[Ziro Games Launcher] launch EmulationStation command={command} cwd={cwd}", xbmc.LOGINFO)
    proc = start_process(command, cwd)
    verify_process_started(proc, process_name)

    ADDON_DATA.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps({
        "mode": "emulationstation",
        "title": "EmulationStation",
        "pid": proc.pid,
        "process_name": process_name,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "return_focus_to_kodi": True,
        "return_path": RETURN_PATH,
    }, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    try:
        mode = (args.get("mode") or "").strip().lower()
        if mode in {"emulationstation", "es"}:
            launch_emulationstation()
        elif "game_id" in args:
            raise RuntimeError("Per-game launching is disabled. Open EmulationStation to play games.")
        else:
            raise RuntimeError("Missing launch mode. Use mode=emulationstation.")
    except Exception as exc:
        xbmc.log(f"[Ziro Games Launcher] failed: {exc}", xbmc.LOGERROR)
        xbmc.executebuiltin(f"ActivateWindow(Programs,{RETURN_PATH},return)")
        xbmcgui.Dialog().notification("Games", str(exc), xbmcgui.NOTIFICATION_ERROR, 6000)


if __name__ == "__main__":
    main()
