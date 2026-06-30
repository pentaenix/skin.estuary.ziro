from __future__ import annotations

import threading

import xbmc
import xbmcgui

from .db import GameDatabase
from .home_state import refresh_home_platform_properties
from .routes import Router
from .scanner import ScanResult

_scan_lock = threading.Lock()
_scan_running = False


def _notify(title: str, message: str, *, error: bool = False) -> None:
    icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
    xbmcgui.Dialog().notification(title, message, icon, 5000)


def _finish_scan(result: ScanResult, *, offer_artwork: bool = False) -> None:
    summary = result.summary()
    headline = summary.splitlines()[0]
    if result.imported:
        _notify("Ziro Games", headline)
    else:
        _notify("Ziro Games", headline, error=True)
        xbmc.log(f"[Ziro Games Scanner] {summary}", xbmc.LOGWARNING)

    refresh_home_platform_properties()
    xbmc.executebuiltin("Container.Refresh")

    if offer_artwork and result.imported:
        xbmc.executebuiltin("RunPlugin(plugin://plugin.program.ziro.games/?path=/offer_artwork)")


def scan_in_background(*, offer_artwork: bool = False) -> bool:
    global _scan_running
    with _scan_lock:
        if _scan_running:
            _notify("Ziro Games", "A library scan is already running.")
            return False
        _scan_running = True

    def job() -> None:
        global _scan_running
        try:
            db = GameDatabase()
            result = Router(db).scan_sources()
            _finish_scan(result, offer_artwork=offer_artwork)
        except Exception as exc:
            xbmc.log(f"[Ziro Games Scanner] background scan failed: {exc}", xbmc.LOGERROR)
            _notify("Ziro Games", f"Scan failed: {exc}", error=True)
        finally:
            with _scan_lock:
                _scan_running = False

    _notify("Ziro Games", "Scanning game library...")
    threading.Thread(target=job, daemon=True).start()
    return True
