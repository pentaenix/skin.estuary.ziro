from __future__ import annotations

import os

import xbmcvfs

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")


def normalize_art_path(path: str) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    path = xbmcvfs.translatePath(path)
    return path.replace("\\", "/")


def _looks_like_image_path(path: str) -> bool:
    lower = path.lower()
    return lower.startswith(("http://", "https://")) or lower.endswith(_IMAGE_SUFFIXES)


def path_exists(path: str) -> bool:
    normalized = normalize_art_path(path)
    if not normalized:
        return False
    if xbmcvfs.exists(normalized):
        return True
    if "://" in normalized:
        return False
    os_path = os.path.normpath(normalized)
    return os.path.isfile(os_path) or os.path.isdir(os_path)


def usable_art_path(path: str, *, trust_if_plausible: bool = False) -> str:
    normalized = normalize_art_path(path)
    if not normalized:
        return ""
    if path_exists(normalized):
        return normalized
    if trust_if_plausible and _looks_like_image_path(normalized):
        return normalized
    return ""
