from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from types import ModuleType

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

PLUGIN_ID = "plugin.program.ziro.games"

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# platform_id -> Games settings key (fallback if plugin module cannot be loaded)
_EMULATOR_SETTING_KEYS: dict[str, str] = {
    "gamecube": "emulator_dolphin",
    "wii": "emulator_dolphin",
    "gba": "emulator_mgba",
    "nes": "emulator_retroarch",
    "snes": "emulator_retroarch",
    "n64": "emulator_retroarch",
    "gb": "emulator_retroarch",
    "gbc": "emulator_retroarch",
    "nds": "emulator_retroarch",
    "ps1": "emulator_retroarch",
    "ps2": "emulator_pcsx2",
    "ps3": "emulator_rpcs3",
    "psp": "emulator_ppsspp",
}

ADDON_DATA = Path(xbmcvfs.translatePath("special://profile/addon_data/plugin.program.ziro.games"))
DB_PATH = ADDON_DATA / "games.db"
SESSION_PATH = ADDON_DATA / "session.json"


def _load_plugin_platforms() -> ModuleType | None:
    plugin_root = xbmcvfs.translatePath(f"special://addons/{PLUGIN_ID}")
    module_path = os.path.join(plugin_root, "resources", "lib", "platforms.py")
    if not os.path.isfile(module_path):
        xbmc.log(f"[Ziro Games Launcher] platforms module missing at {module_path}", xbmc.LOGWARNING)
        return None
    spec = importlib.util.spec_from_file_location("ziro_games_platforms", module_path)
    if spec is None or spec.loader is None:
        xbmc.log(f"[Ziro Games Launcher] failed to load platforms spec from {module_path}", xbmc.LOGWARNING)
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PLATFORMS = _load_plugin_platforms()


def _emulator_setting_key(platform_id: str) -> str:
    if _PLATFORMS is not None:
        platform = _PLATFORMS.get_platform(platform_id)
        if platform is not None:
            return platform.emulator_setting
    return _EMULATOR_SETTING_KEYS.get(platform_id, "")


def _resolve_core_path(executable: str, platform_id: str) -> str:
    if _PLATFORMS is None:
        return ""
    platform = _PLATFORMS.get_platform(platform_id)
    if platform is None:
        return ""
    return _PLATFORMS.resolve_core_path(executable, platform.retroarch_core)


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
    setting_key = _emulator_setting_key(platform_id)
    candidates: list[str] = []
    db_exe = (profile.get("executable_path") or "").strip()
    if db_exe:
        candidates.extend(_path_candidates(db_exe))
    if setting_key:
        setting_exe = (addon.getSetting(setting_key) or "").strip()
        if setting_exe:
            candidates.extend(_path_candidates(setting_exe))
    for candidate in candidates:
        if _path_exists(candidate):
            return _normalize_launch_path(candidate)
    fallback = db_exe or ((addon.getSetting(setting_key) or "").strip() if setting_key else "")
    return _normalize_launch_path(fallback)


def resolve_rom_path(rom_path: str) -> str:
    for candidate in _path_candidates(rom_path):
        if _path_exists(candidate):
            return _normalize_launch_path(candidate)
    return _normalize_launch_path((rom_path or "").strip())


def build_launch_command(
    executable_path: str,
    rom_path: str,
    platform_id: str,
    profile: dict,
    core_path: str,
) -> list[str]:
    """Build argv without shell parsing so paths with spaces/! stay intact."""
    if platform_id in {"gamecube", "wii"}:
        return [
            executable_path,
            "-b",
            "-e",
            rom_path,
            "-C",
            "Dolphin.Display.Fullscreen=True",
            "-C",
            "GFX.BorderlessFullscreen=False",
            "-C",
            "Dolphin.Interface.ConfirmStop=False",
        ]
    if platform_id == "gba":
        return [executable_path, "-f", rom_path]
    if platform_id == "ps2":
        return [executable_path, "-batch", "-nogui", rom_path]
    if core_path:
        return [executable_path, "-L", core_path, rom_path]

    template = (profile.get("arguments_template") or "").strip()
    if not template or template in {'"{rom_path}"', '"{rom_path}"'}:
        return [executable_path, rom_path]

    # Last resort for uncommon templates: one shell line, hidden console.
    args = template.format(
        rom_path=rom_path,
        rom_dir=str(Path(rom_path).parent),
        rom_file=Path(rom_path).name,
        rom_name=Path(rom_path).stem,
        executable_path=executable_path,
        core_path=core_path,
    )
    command_line = subprocess.list2cmdline([executable_path]) + " " + args
    return [command_line]  # sentinel: caller uses shell mode


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
    if os.name != "nt":
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

    if len(command) == 1:
        popen_kwargs["shell"] = True
        return subprocess.Popen(command[0], **popen_kwargs)
    return subprocess.Popen(command, **popen_kwargs)


def verify_process_started(proc: subprocess.Popen, process_name: str) -> None:
    deadline = time.time() + 12.0
    while time.time() < deadline:
        if process_running(process_name):
            bring_pid_to_front(proc.pid)
            return
        if os.name != "nt" and proc.poll() is not None:
            raise RuntimeError(f"Emulator exited immediately (code {proc.returncode})")
        time.sleep(0.25)
    code = proc.poll()
    if code is not None:
        raise RuntimeError(f"Emulator exited immediately (code {code}). Check emulator path and ROM.")
    raise RuntimeError(f"Emulator did not start ({process_name}). Check Games settings and kodi.log.")


def bring_pid_to_front(pid: int, retries: int = 24) -> None:
    """Raise the emulator window above Kodi without minimizing Kodi."""
    if os.name != "nt" or pid <= 0:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_SHOW = 5
        user32.AllowSetForegroundWindow(pid)

        for _ in range(retries):
            found = False

            def callback(hwnd: int, _lparam: int) -> bool:
                nonlocal found
                proc_id = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                if proc_id.value != pid or not user32.IsWindowVisible(hwnd):
                    return True
                user32.ShowWindow(hwnd, SW_SHOW)
                user32.SetForegroundWindow(hwnd)
                found = True
                return False

            enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(callback)
            user32.EnumWindows(enum_proc, 0)
            if found:
                return
            time.sleep(0.25)
    except Exception as exc:
        xbmc.log(f"[Ziro Games Launcher] bring to front failed: {exc}", xbmc.LOGDEBUG)


def restore_kodi() -> None:
    xbmc.executebuiltin("ActivateWindow(Home)")


def launch(game_id: int) -> None:
    game, profile = get_launch_data(game_id)
    platform_id = game["platform_id"]
    executable_path = resolve_executable_path(profile, platform_id)
    rom_path = resolve_rom_path(game["rom_path"])
    if not executable_path:
        raise RuntimeError("Emulator path not configured. Set it in Games settings, then scan.")
    if not xbmcvfs.exists(executable_path):
        raise RuntimeError(f"Emulator executable missing: {executable_path}")
    if not xbmcvfs.exists(rom_path):
        raise RuntimeError(f"Game file not found: {rom_path}")

    core_path = _resolve_core_path(executable_path, platform_id)
    command = build_launch_command(executable_path, rom_path, platform_id, profile, core_path)
    cwd = profile.get("working_directory") or str(Path(executable_path).parent)
    if cwd and not xbmcvfs.exists(cwd):
        cwd = str(Path(executable_path).parent)
    process_name = Path(executable_path).name

    xbmc.log(f"[Ziro Games Launcher] launch game={game['title']} command={command} cwd={cwd}", xbmc.LOGINFO)
    proc = start_process(command, cwd)
    verify_process_started(proc, process_name)

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
        restore_kodi()
        xbmcgui.Dialog().notification("Games", str(exc), xbmcgui.NOTIFICATION_ERROR, 6000)


if __name__ == "__main__":
    main()
