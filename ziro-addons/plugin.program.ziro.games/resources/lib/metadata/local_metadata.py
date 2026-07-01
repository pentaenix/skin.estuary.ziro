from __future__ import annotations

import html
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
VIDEO_SUFFIXES = {".mp4", ".webm", ".m4v", ".avi", ".mkv", ".mov"}

_GAMELIST_CACHE: dict[str, dict[str, dict]] = {}
_SKRAPER_DAT_CACHE: dict[str, dict[str, dict]] = {}

# Skraper media folders (under media/)
SKRAPER_MEDIA_DIRS = {
    "cover_path": ("box2dfront", "box2d", "boxfront", "boxart"),
    "fanart_path": ("screenshot", "screenshots"),
    "screenshot_path": ("screenshottitle", "title", "titlescreen"),
    "video_path": ("videos", "video"),
}

ES_MEDIA_DIRS = {
    "cover_path": ("box2d", "boxart", "covers", "images"),
    "fanart_path": ("fanart", "fanarts", "backdrops"),
    "logo_path": ("marquee", "wheel", "logos", "wheels"),
    "screenshot_path": ("screenshot", "screenshots", "ss"),
    "video_path": ("videos", "video"),
}


def clear_gamelist_cache() -> None:
    _GAMELIST_CACHE.clear()
    _SKRAPER_DAT_CACHE.clear()


def _norm_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def _basename_key(path: str) -> str:
    return _norm_path(path).split("/")[-1].lower()


def _normalize_match_key(text: str) -> str:
    value = html.unescape(text or "").lower()
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


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


def _list_files(folder: str) -> list[str]:
    if not folder or not xbmcvfs.exists(folder):
        return []
    try:
        _dirs, files = xbmcvfs.listdir(folder)
        return [os.path.join(folder, name) for name in files]
    except Exception:
        return []


def _list_dirs(folder: str) -> list[str]:
    if not folder or not xbmcvfs.exists(folder):
        return []
    try:
        dirs, _files = xbmcvfs.listdir(folder)
        return [name for name in dirs if name not in {".", ".."}]
    except Exception:
        return []


def _folder_has_local_metadata(folder: str) -> bool:
    if xbmcvfs.exists(os.path.join(folder, "gamelist.xml")):
        return True
    if xbmcvfs.exists(os.path.join(folder, "media")):
        return True
    for file_path in _list_files(folder):
        if file_path.lower().endswith(".dat"):
            return True
    return False


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
        "description": html.unescape(text("desc")),
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


def _skraper_game_to_metadata(game_node: ET.Element) -> dict:
    title = (game_node.attrib.get("name") or "").strip()

    def text(tag: str) -> str:
        node = game_node.find(tag)
        return html.unescape((node.text or "").strip()) if node is not None else ""

    manufacturer = text("manufacturer")
    metadata = {
        "title": title,
        "description": text("description"),
        "developer": manufacturer,
        "publisher": manufacturer,
        "genres": text("genre"),
    }
    year = _parse_release_year(text("year"))
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


def _find_skraper_dat_file(folder: str) -> str:
    for file_path in _list_files(folder):
        if file_path.lower().endswith(".dat"):
            return file_path
    return ""


def _load_skraper_dat_index(folder: str) -> dict[str, dict]:
    folder = folder.rstrip("/\\")
    if folder in _SKRAPER_DAT_CACHE:
        return _SKRAPER_DAT_CACHE[folder]

    index: dict[str, dict] = {}
    dat_path = _find_skraper_dat_file(folder)
    if not dat_path:
        _SKRAPER_DAT_CACHE[folder] = index
        return index

    try:
        tree = ET.parse(dat_path)
        root = tree.getroot()
        for game_node in root.findall("game"):
            metadata = _skraper_game_to_metadata(game_node)
            metadata["skraper_game_name"] = metadata.get("title") or ""
            for rom_node in game_node.findall("rom"):
                rom_name = (rom_node.attrib.get("name") or "").strip()
                if not rom_name:
                    continue
                key = _basename_key(rom_name)
                if key:
                    index[key] = dict(metadata)
    except Exception as exc:
        xbmc.log(f"[Ziro Games] Skraper .dat parse failed path={dat_path}: {exc}", xbmc.LOGWARNING)

    _SKRAPER_DAT_CACHE[folder] = index
    return index


def find_source_folder(rom_path: str, source_folder: str = "") -> str:
    if source_folder and xbmcvfs.exists(source_folder):
        return source_folder.rstrip("/\\")
    rom = _norm_path(rom_path)
    parts = rom.split("/")
    for depth in range(len(parts) - 1, 0, -1):
        candidate = "/".join(parts[:depth])
        if _folder_has_local_metadata(candidate):
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


def lookup_skraper_dat_metadata(rom_path: str, *, source_folder: str = "") -> dict:
    folder = find_source_folder(rom_path, source_folder)
    index = _load_skraper_dat_index(folder)
    basename = _basename_key(rom_path)
    if basename in index:
        return dict(index[basename])
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


def _score_name_match(file_stem: str, *needles: str) -> int:
    file_key = _normalize_match_key(file_stem)
    if not file_key:
        return 0
    best = 0
    for needle in needles:
        key = _normalize_match_key(needle)
        if not key:
            continue
        if file_key == key:
            return 1000 + len(key)
        if file_key.startswith(key) or key.startswith(file_key):
            best = max(best, 500 + min(len(file_key), len(key)))
        elif key in file_key or file_key in key:
            best = max(best, 200 + min(len(file_key), len(key)))
    return best


def _find_media_in_folder(folder: str, *needles: str, suffixes: set[str]) -> str:
    if not folder or not xbmcvfs.exists(folder):
        return ""
    best_path = ""
    best_score = 0
    for file_path in _list_files(folder):
        suffix = Path(file_path).suffix.lower()
        if suffix not in suffixes:
            continue
        score = _score_name_match(Path(file_path).stem, *needles)
        if score > best_score:
            best_score = score
            best_path = file_path
    return best_path if best_score >= 200 else ""


def _discover_skraper_media(folder: str, game_name: str, rom_stem: str) -> dict:
    found: dict[str, str] = {}
    media_root = os.path.join(folder, "media")
    if not xbmcvfs.exists(media_root):
        return found

    available_dirs = {name.lower(): os.path.join(media_root, name) for name in _list_dirs(media_root)}
    needles = (game_name, rom_stem, rom_stem.replace("_", " "), rom_stem.replace("-", " "))

    for field, dir_names in SKRAPER_MEDIA_DIRS.items():
        suffixes = VIDEO_SUFFIXES if field == "video_path" else IMAGE_SUFFIXES
        for dir_name in dir_names:
            media_dir = available_dirs.get(dir_name.lower())
            if not media_dir:
                continue
            path = _find_media_in_folder(media_dir, *needles, suffixes=suffixes)
            if path:
                found[field] = path
                break
    return found


def discover_local_art(rom_path: str, *, source_folder: str = "", game_name: str = "") -> dict:
    folder = find_source_folder(rom_path, source_folder)
    rom_dir = os.path.dirname(rom_path.replace("/", os.sep))
    stem = _stem(rom_path)
    title_guess = game_name or stem.replace("_", " ").replace("-", " ")

    skraper = _discover_skraper_media(folder, title_guess, stem)
    if skraper:
        return skraper

    media_roots = [folder, rom_dir]
    found: dict[str, str] = {}
    name_variants = {
        _normalize_match_key(stem),
        _normalize_match_key(title_guess),
    }

    for field, dirs in ES_MEDIA_DIRS.items():
        suffixes = VIDEO_SUFFIXES if field == "video_path" else IMAGE_SUFFIXES
        candidates: list[str] = []
        for root in media_roots:
            for subdir in ("media", "downloaded_media", "images", ""):
                for media_name in dirs:
                    base = os.path.join(root, subdir, media_name) if subdir else os.path.join(root, media_name)
                    for variant in name_variants:
                        if not variant:
                            continue
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
    metadata = lookup_skraper_dat_metadata(rom_path, source_folder=source_folder)
    if not metadata:
        metadata = lookup_gamelist_metadata(rom_path, source_folder=source_folder)

    game_name = metadata.get("title") or metadata.get("skraper_game_name") or ""
    discovered = discover_local_art(rom_path, source_folder=source_folder, game_name=game_name)

    for key, value in discovered.items():
        if value and not metadata.get(key):
            metadata[key] = value

    # Skraper: title screen works well as a logo overlay on the box art.
    if metadata.get("screenshot_path") and not metadata.get("logo_path"):
        metadata["logo_path"] = metadata["screenshot_path"]

    metadata.pop("skraper_game_name", None)
    return metadata


def list_local_art_options(rom_path: str, art_kind: str) -> list[tuple[str, str]]:
    folder = find_source_folder(rom_path)
    stem = _stem(rom_path)
    meta = lookup_local_metadata(rom_path)
    needles = (meta.get("title") or "", stem, stem.replace("_", " "), stem.replace("-", " "))

    skraper_dirs = {
        "cover": SKRAPER_MEDIA_DIRS["cover_path"],
        "fanart": SKRAPER_MEDIA_DIRS["fanart_path"],
        "logo": SKRAPER_MEDIA_DIRS["screenshot_path"],
        "screenshot": SKRAPER_MEDIA_DIRS["screenshot_path"],
        "video": SKRAPER_MEDIA_DIRS["video_path"],
    }.get(art_kind, SKRAPER_MEDIA_DIRS["cover_path"])

    es_dirs = {
        "cover": ES_MEDIA_DIRS["cover_path"],
        "fanart": ES_MEDIA_DIRS["fanart_path"],
        "logo": ES_MEDIA_DIRS["logo_path"],
        "screenshot": ES_MEDIA_DIRS["screenshot_path"],
        "video": ES_MEDIA_DIRS["video_path"],
    }.get(art_kind, ES_MEDIA_DIRS["cover_path"])

    suffixes = VIDEO_SUFFIXES if art_kind == "video" else IMAGE_SUFFIXES
    options: list[tuple[str, str]] = []
    seen: set[str] = set()

    for subroot in (folder, os.path.dirname(rom_path.replace("/", os.sep))):
        for subdir in ("media", "downloaded_media", "images"):
            for media_name in (*skraper_dirs, *es_dirs):
                base = os.path.join(subroot, subdir, media_name)
                if not xbmcvfs.exists(base):
                    continue
                for file_path in _list_files(base):
                    entry = Path(file_path)
                    if entry.suffix.lower() not in suffixes:
                        continue
                    if _score_name_match(entry.stem, *needles) < 200:
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
    has_content = any(
        metadata.get(key)
        for key in ("cover_path", "fanart_path", "screenshot_path", "video_path", "description")
    )
    if not has_content:
        return "no_match", "No Skraper metadata found near this ROM (look for .dat and media/ folders)"

    apply_local_metadata(db, game_id, metadata)
    return "ok", "Local metadata imported"
