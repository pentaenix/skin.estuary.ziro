from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path

import xbmc
import xbmcvfs

SESSION_PATH = Path(xbmcvfs.translatePath("special://profile/addon_data/plugin.program.ziro.games/session.json"))


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    system = platform.system().lower()
    if system == "windows":
        try:
            out = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}"], text=True, stderr=subprocess.DEVNULL)
            return str(pid) in out
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def focus_kodi() -> None:
    system = platform.system().lower()
    if system == "windows":
        try:
            subprocess.Popen([
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                "$wshell = New-Object -ComObject WScript.Shell; $wshell.AppActivate('Kodi') | Out-Null"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            xbmc.log(f"[Ziro Games Service] focus Kodi failed: {exc}", xbmc.LOGWARNING)
    else:
        xbmc.executebuiltin("ActivateWindow(Home)")


def main() -> None:
    monitor = xbmc.Monitor()
    xbmc.log("[Ziro Games Service] started", xbmc.LOGINFO)
    last_pid = None
    while not monitor.abortRequested():
        if SESSION_PATH.exists():
            try:
                data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
                pid = int(data.get("pid", 0))
                if pid != last_pid:
                    xbmc.log(f"[Ziro Games Service] watching pid={pid} title={data.get('title')}", xbmc.LOGINFO)
                    last_pid = pid
                if pid and not pid_alive(pid):
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
