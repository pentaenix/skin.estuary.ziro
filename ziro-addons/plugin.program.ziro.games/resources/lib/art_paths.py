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


def _path_candidates(path: str) -> list[str]:
    normalized = normalize_art_path(path)
    if not normalized:
        return []
    candidates = [normalized, os.path.normpath(normalized)]
    if len(normalized) > 2 and normalized[1] == ":":
        candidates.append(normalized.replace("/", "\\"))
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def path_exists(path: str) -> bool:
    for candidate in _path_candidates(path):
        if xbmcvfs.exists(candidate):
            return True
        if "://" not in candidate and (os.path.isfile(candidate) or os.path.isdir(candidate)):
            return True
    return False


def usable_art_path(path: str, *, trust_if_plausible: bool = False) -> str:
    for candidate in _path_candidates(path):
        if path_exists(candidate):
            return candidate.replace("\\", "/")
    normalized = normalize_art_path(path)
    if trust_if_plausible and normalized and _looks_like_image_path(normalized):
        return normalized
    return ""
