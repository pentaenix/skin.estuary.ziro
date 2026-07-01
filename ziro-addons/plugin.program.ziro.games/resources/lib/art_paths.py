from __future__ import annotations

import os

import xbmcvfs


def normalize_art_path(path: str) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    path = xbmcvfs.translatePath(path)
    return path.replace("\\", "/")


def path_exists(path: str) -> bool:
    normalized = normalize_art_path(path)
    if not normalized:
        return False
    if xbmcvfs.exists(normalized):
        return True
    os_path = os.path.normpath(normalized)
    return os.path.isfile(os_path) or os.path.isdir(os_path)


def usable_art_path(path: str) -> str:
    normalized = normalize_art_path(path)
    return normalized if path_exists(normalized) else ""
