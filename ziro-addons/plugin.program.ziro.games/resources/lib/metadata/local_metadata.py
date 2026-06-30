from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import xbmc
import xbmcvfs

from ..db import GameDatabase
from .genre_sync import map_genre_names_to_ids

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".webm", ".m4v", ".avi", ".mkv"}

_GAMELIST_CACHE: dict[str, dict[str, dict]] = {}


def clear_gamelist_cache() -> None:
    _GAMELIST_CACHE.clear()


def _norm_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def _basename_key(path: str) -> str:
    return _norm_path(path).split("/")[-1].lower()


def _resolve_path(base_dir: str, relative: str) -> str:
    relative = (relative or "").strip()
    if not relative:
        return ""
    if relative.startswith("./"):
        relative = relative[2:]
    joined = os.path.join(base_dir, relative.replace("/", os.sep))
    candidates = [joined, xbmcvfs.translatePath(joined)]
    for candidate in candidates:
        if candidate and xbmcvfs.exists(candidate):
            return candidate
    return joined


def _parse_release_year(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    match = re.match(r"(\d{4})", text)
    if match:
        return int(match.group(1))
    return None


def _parse_genres(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[,;/]", value) if part.strip()]


def _game_entry_to_metadata(entry: ET.Element, base_dir: str) -> dict:
    def text(tag: str) -> str:
        node = entry.find(tag)
        return (node.text or "").strip() if node is not None else ""

    cover = text("image") or text("thumbnail")
    fanart = text("fanart")
    logo = text("marquee") or text("wheel")
    screenshot = text("screenshot") or text("ss")
    video = text("video")

    metadata = {
        "title": text("name"),
        "description": text("desc"),
        "developer": text("developer"),
        "publisher": text("publisher"),
        "genres": text("genre"),
        "cover_path": _resolve_path(base_dir, cover) if cover else "",
        "fanart_path": _resolve_path(base_dir, fanart) if fanart else "",
        "logo_path": _resolve_path(base_dir, logo) if logo else "",
        "screenshot_path": _resolve_path(base_dir, screenshot) if screenshot else "",
        "video_path": _resolve_path(base_dir, video) if video else "",
    }
    year = _parse_release_year(text("releasedate"))
    if year:
        metadata["release_year"] = year
    return metadata


def _load_gamelist_index(folder: str) -> dict[str, dict]:
    folder = folder.rstrip("/\\")
    if folder in _GAMELIST_CACHE:
        return _GAMELIST_CACHE[folder]

    index: dict[str, dict] = {}
    gamelist_path = os.path.join(folder, "gamelist.xml")
    if not xbmcvfs.exists(gamelist_path):
        _GAMELIST_CACHE[folder] = index
        return index

    try:
        tree = ET.parse(gamelist_path)
        root = tree.getroot()
        for game_node in root.findall("game"):
            entry_path = (game_node.findtext("path") or "").strip()
            if not entry_path:
                continue
            metadata = _game_entry_to_metadata(game_node, folder)
            resolved_rom = _resolve_path(folder, entry_path)
            keys = {
                _basename_key(entry_path),
                _basename_key(resolved_rom),
            }
            rel = _norm_path(entry_path)
            if rel.startswith("./"):
                rel = rel[2:]
            keys.add(_norm_path(rel).lower())
            for key in keys:
                if key:
                    index[key] = metadata
    except Exception as exc:
        xbmc.log(f"[Ziro Games] gamelist.xml parse failed folder={folder}: {exc}", xbmc.LOGWARNING)

    _GAMELIST_CACHE[folder] = index
    return index


def find_source_folder(rom_path: str, source_folder: str = "") -> str:
    if source_folder and xbmcvfs.exists(source_folder):
        return source_folder.rstrip("/\\")
    rom = _norm_path(rom_path)
    parts = rom.split("/")
    for depth in range(len(parts) - 1, 0, -1):
        candidate = "/".join(parts[:depth])
        if xbmcvfs.exists(os.path.join(candidate, "gamelist.xml")):
            return candidate
    return os.path.dirname(rom_path.replace("/", os.sep))


def lookup_gamelist_metadata(rom_path: str, *, source_folder: str = "") -> dict:
    folder = find_source_folder(rom_path, source_folder)
    index = _load_gamelist_index(folder)
    basename = _basename_key(rom_path)
    if basename in index:
        return dict(index[basename])

    rel_from_folder = _norm_path(rom_path)
    if folder and rel_from_folder.lower().startswith(_norm_path(folder).lower()):
        rel = rel_from_folder[len(_norm_path(folder)) :].lstrip("/").lower()
        if rel in index:
            return dict(index[rel])
    return {}


def _stem(path: str) -> str:
    name = _basename_key(path)
    if "." in name:
        return name.rsplit(".", 1)[0]
    return name


def _first_existing(paths: list[str]) -> str:
    for path in paths:
        if path and xbmcvfs.exists(path):
            return path
    return ""


def discover_local_art(rom_path: str, *, source_folder: str = "") -> dict:
    folder = find_source_folder(rom_path, source_folder)
    rom_dir = os.path.dirname(rom_path.replace("/", os.sep))
    stem = _stem(rom_path)
    title_guess = stem.replace("_", " ").replace("-", " ")

    media_roots = [folder, rom_dir]
    subdirs = {
        "cover_path": ("box2d", "boxart", "covers", "images"),
        "fanart_path": ("fanart", "fanarts", "backdrops"),
        "logo_path": ("marquee", "wheel", "logos", "wheels"),
        "screenshot_path": ("screenshot", "screenshots", "ss"),
        "video_path": ("videos", "video"),
    }

    found: dict[str, str] = {}
    name_variants = {stem, stem.replace(" ", ""), title_guess, title_guess.replace(" ", "")}

    for field, dirs in subdirs.items():
        suffixes = VIDEO_SUFFIXES if field == "video_path" else IMAGE_SUFFIXES
        candidates: list[str] = []
        for root in media_roots:
            for subdir in ("media", "downloaded_media", "images", ""):
                for media_name in dirs:
                    base = os.path.join(root, subdir, media_name) if subdir else os.path.join(root, media_name)
                    for variant in name_variants:
                        for suffix in suffixes:
                            candidates.append(os.path.join(base, f"{variant}{suffix}"))
            for suffix in suffixes:
                candidates.append(os.path.join(rom_dir, f"{stem}{suffix}"))
                candidates.append(os.path.join(rom_dir, f"{stem}-image{suffix}"))
        path = _first_existing(candidates)
        if path:
            found[field] = path
    return found


def lookup_local_metadata(rom_path: str, *, source_folder: str = "") -> dict:
    metadata = lookup_gamelist_metadata(rom_path, source_folder=source_folder)
    discovered = discover_local_art(rom_path, source_folder=source_folder)
    for key, value in discovered.items():
        if value and not metadata.get(key):
            metadata[key] = value
    return metadata


def _list_files(folder: str) -> list[str]:
    if not folder or not xbmcvfs.exists(folder):
        return []
    try:
        _dirs, files = xbmcvfs.listdir(folder)
        return [os.path.join(folder, name) for name in files]
    except Exception:
        return []


def list_local_art_options(rom_path: str, art_kind: str) -> list[tuple[str, str]]:
    folder = find_source_folder(rom_path)
    stem = _stem(rom_path)
    kind_dirs = {
        "cover": ("box2d", "boxart", "covers", "images"),
        "fanart": ("fanart", "fanarts"),
        "logo": ("marquee", "wheel", "logos"),
        "screenshot": ("screenshot", "screenshots", "ss"),
    }.get(art_kind, ("box2d",))

    options: list[tuple[str, str]] = []
    seen: set[str] = set()
    for subroot in (folder, os.path.dirname(rom_path.replace("/", os.sep))):
        for subdir in ("media", "downloaded_media", "images"):
            for media_name in kind_dirs:
                base = os.path.join(subroot, subdir, media_name)
                if not xbmcvfs.exists(base):
                    continue
                for file_path in _list_files(base):
                    entry = Path(file_path)
                    if entry.suffix.lower() not in IMAGE_SUFFIXES:
                        continue
                    if stem not in entry.stem.lower().replace(" ", ""):
                        continue
                    path = str(entry)
                    if path in seen:
                        continue
                    seen.add(path)
                    options.append((entry.name, path))
    return options


def apply_local_metadata(db: GameDatabase, game_id: int, metadata: dict) -> dict:
    updates: dict = {"metadata_updated_at": datetime.now().isoformat(timespec="seconds")}
    for field in (
        "title",
        "description",
        "developer",
        "publisher",
        "release_year",
        "cover_path",
        "fanart_path",
        "logo_path",
        "screenshot_path",
        "video_path",
    ):
        value = metadata.get(field)
        if value in (None, ""):
            continue
        if field.endswith("_path") and not xbmcvfs.exists(str(value)):
            continue
        updates[field] = value

    if updates.get("title"):
        db.execute(
            "UPDATE games SET title=?, sort_title=? WHERE id=?",
            (updates["title"], updates["title"].lower(), game_id),
        )
        updates.pop("title", None)

    db.update_game_artwork(game_id, updates)

    genre_names = _parse_genres(metadata.get("genres") or "")
    genre_ids = map_genre_names_to_ids(genre_names)
    if genre_ids:
        db.set_game_genres(game_id, genre_ids)

    return updates


def import_metadata_for_game(
    db: GameDatabase,
    game_id: int,
    *,
    source_folder: str = "",
    force: bool = False,
) -> tuple[str, str]:
    game = db.get_game(game_id)
    if not game:
        return "missing", "Game not found"
    if int(game.get("manual_metadata_locked") or 0) and not force:
        return "locked", "Manual metadata lock enabled"

    rom_path = game.get("rom_path") or ""
    metadata = lookup_local_metadata(rom_path, source_folder=source_folder)
    if not metadata.get("cover_path") and not metadata.get("description"):
        return "no_match", "No Skraper/gamelist.xml metadata found near this ROM"

    apply_local_metadata(db, game_id, metadata)
    return "ok", "Local metadata imported"
