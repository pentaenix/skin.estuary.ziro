from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcvfs

PLUGIN_ID = "plugin.program.ziro.games"
SESSION_PATH = Path(xbmcvfs.translatePath(f"special://profile/addon_data/{PLUGIN_ID}/session.json"))
SESSION_GRACE_SECONDS = 10


def _plugin_installed() -> bool:
    if not xbmc.getCondVisibility(f"System.HasAddon({PLUGIN_ID})"):
        return False
    try:
        xbmcaddon.Addon(PLUGIN_ID)
        return True
    except Exception:
        return False


def _ensure_plugin_path() -> str:
    root = xbmcvfs.translatePath(f"special://addons/{PLUGIN_ID}")
    if not root:
        raise FileNotFoundError(f"{PLUGIN_ID} addon path is empty")
    if not xbmcvfs.exists(root) and not os.path.isdir(root):
        raise FileNotFoundError(f"{PLUGIN_ID} is not installed at {root}")
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    system = platform.system().lower()
    if system == "windows":
        try:
            out = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}"], text=True, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return str(pid) in out
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def process_running(process_name: str) -> bool:
    if not process_name:
        return False
    if platform.system().lower() != "windows":
        return False
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return process_name.lower() in out.lower()
    except Exception:
        return False


def _session_age_seconds(data: dict) -> float | None:
    started = data.get("started_at")
    if not started:
        return None
    try:
        return (datetime.now() - datetime.fromisoformat(str(started))).total_seconds()
    except Exception:
        return None


def session_still_active(data: dict) -> bool:
    age = _session_age_seconds(data)
    if age is not None and age < SESSION_GRACE_SECONDS:
        return True

    process_name = (data.get("process_name") or "").strip()
    if process_name and process_running(process_name):
        return True

    pid = int(data.get("pid", 0))
    return bool(pid and pid_alive(pid))


def focus_kodi() -> None:
    xbmc.executebuiltin("ActivateWindow(Home)")


def refresh_home_state(monitor: xbmc.Monitor | None = None) -> None:
    wait = monitor or xbmc.Monitor()
    for _ in range(20):
        if _plugin_installed():
            break
        if wait.waitForAbort(0.25):
            return
    if not _plugin_installed():
        raise FileNotFoundError(f"{PLUGIN_ID} is not installed")

    _ensure_plugin_path()
    import importlib

    db_module = importlib.import_module("resources.lib.db")
    scanner_module = importlib.import_module("resources.lib.scanner")
    home_module = importlib.import_module("resources.lib.home_state")
    db = db_module.GameDatabase()
    scanner_module.purge_junk_games(db)
    db.clear_play_state_for_hidden_games()
    home_module.refresh_home_widgets(db)


def main() -> None:
    monitor = xbmc.Monitor()
    xbmc.log("[Ziro Games Service] started", xbmc.LOGINFO)
    try:
        refresh_home_state(monitor)
    except Exception as exc:
        xbmc.log(f"[Ziro Games Service] home refresh failed: {exc}", xbmc.LOGWARNING)
        if _plugin_installed():
            xbmc.executebuiltin(f"RunPlugin(plugin://{PLUGIN_ID}/?path=/sync_home)")
    last_pid = None
    while not monitor.abortRequested():
        if SESSION_PATH.exists():
            try:
                data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
                pid = int(data.get("pid", 0))
                if pid != last_pid:
                    xbmc.log(
                        f"[Ziro Games Service] watching pid={pid} process={data.get('process_name')} title={data.get('title')}",
                        xbmc.LOGINFO,
                    )
                    last_pid = pid
                if not session_still_active(data):
                    xbmc.log(f"[Ziro Games Service] session ended pid={pid}", xbmc.LOGINFO)
                    SESSION_PATH.unlink(missing_ok=True)
                    if data.get("return_focus_to_kodi", True):
                        focus_kodi()
                    last_pid = None
            except Exception as exc:
                xbmc.log(f"[Ziro Games Service] session read failed: {exc}", xbmc.LOGWARNING)
        if monitor.waitForAbort(2):
            break


if __name__ == "__main__":
    main()
