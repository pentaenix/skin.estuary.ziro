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
from ..art_paths import normalize_art_path, path_exists, usable_art_path
from .genre_sync import map_genre_names_to_ids
from ..text_utils import clean_display_text, resolve_game_description

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".webm", ".m4v", ".avi", ".mkv", ".mov"}

_GAMELIST_CACHE: dict[str, dict[str, dict]] = {}
_SKRAPER_DAT_CACHE: dict[str, dict[str, dict]] = {}

REGION_TAG_RE = re.compile(r"\s*[\(\[].*?[\)\]]", re.IGNORECASE)

PLATFORM_DAT_FILES: dict[str, tuple[str, ...]] = {
    "wii": ("wii.dat",),
    "gamecube": ("gamecube.dat", "gc.dat"),
    "dreamcast": ("dreamcast.dat",),
    "gba": ("gba.dat",),
    "nds": ("nds.dat",),
    "snes": ("snes.dat",),
    "nes": ("nes.dat",),
    "n64": ("n64.dat",),
    "ps1": ("psx.dat", "ps1.dat", "sony playstation.dat"),
    "ps2": ("ps2.dat",),
    "psp": ("psp.dat",),
}

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
    value = REGION_TAG_RE.sub("", value)
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _read_xml_root(path: str) -> ET.Element | None:
    if not path or not path_exists(path):
        return None
    try:
        handle = xbmcvfs.File(path)
        data = handle.read()
        handle.close()
        if isinstance(data, bytes):
            text = ""
            for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
                try:
                    text = data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if not text:
                text = data.decode("utf-8", errors="replace")
        else:
            text = data or ""
        text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.IGNORECASE)
        return ET.fromstring(text)
    except Exception as exc:
        xbmc.log(f"[Games] XML parse failed path={path}: {exc}", xbmc.LOGWARNING)
        return None


def _rom_lookup_keys(rom_name: str) -> set[str]:
    keys: set[str] = set()
    base = _basename_key(rom_name)
    if not base:
        return keys
    keys.add(base)
    stem = base.rsplit(".", 1)[0] if "." in base else base
    if stem:
        keys.add(stem)
        stripped = REGION_TAG_RE.sub("", stem).strip()
        if stripped:
            keys.add(stripped)
            if "." in base:
                ext = base.rsplit(".", 1)[-1]
                keys.add(f"{stripped}.{ext}")
    return {key for key in keys if key}


def _resolve_path(base_dir: str, relative: str) -> str:
    relative = (relative or "").strip()
    if not relative:
        return ""
    if relative.startswith("./"):
        relative = relative[2:]
    joined = os.path.join(base_dir, relative.replace("/", os.sep))
    candidates = [joined, xbmcvfs.translatePath(joined)]
    for candidate in candidates:
        if candidate and path_exists(candidate):
            return normalize_art_path(candidate)
    return normalize_art_path(joined)


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
    if not folder or not path_exists(folder):
        return []
    try:
        _dirs, files = xbmcvfs.listdir(folder)
        return [os.path.join(folder, name) for name in files]
    except Exception:
        return []


def _list_dirs(folder: str) -> list[str]:
    if not folder or not path_exists(folder):
        return []
    try:
        dirs, _files = xbmcvfs.listdir(folder)
        return [name for name in dirs if name not in {".", ".."}]
    except Exception:
        return []


def _folder_has_local_metadata(folder: str) -> bool:
    if path_exists(os.path.join(folder, "gamelist.xml")):
        return True
    if path_exists(os.path.join(folder, "media")):
        return True
    for file_path in _list_files(folder):
        if file_path.lower().endswith(".dat"):
            return True
    return False


def _rom_file_stems(rom_path: str, game_name: str = "") -> list[str]:
    stems: list[str] = []
    raw_name = _norm_path(rom_path).split("/")[-1]
    if raw_name and "." in raw_name:
        stems.append(raw_name.rsplit(".", 1)[0])
    elif raw_name:
        stems.append(raw_name)
    if game_name and game_name.strip() and game_name.strip() not in stems:
        stems.append(game_name.strip())
    return stems


def _discover_skraper_media_by_name(folder: str, rom_path: str, game_name: str) -> dict:
    """Match Skraper files named after the ROM file (most common layout)."""
    found: dict[str, str] = {}
    media_root = os.path.join(folder, "media")
    if not path_exists(media_root):
        return found

    available_dirs = {name.lower(): os.path.join(media_root, name) for name in _list_dirs(media_root)}
    stems = _rom_file_stems(rom_path, game_name)

    for field, dir_names in SKRAPER_MEDIA_DIRS.items():
        suffixes = VIDEO_SUFFIXES if field == "video_path" else IMAGE_SUFFIXES
        for dir_name in dir_names:
            media_dir = available_dirs.get(dir_name.lower())
            if not media_dir:
                continue
            for stem in stems:
                for suffix in suffixes:
                    candidate = os.path.join(media_dir, f"{stem}{suffix}")
                    usable = usable_art_path(candidate)
                    if usable:
                        found[field] = usable
                        break
                if found.get(field):
                    break
            if found.get(field):
                continue
    return found


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
        "description": clean_display_text(text("desc")),
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


def _skraper_game_to_metadata(game_node: ET.Element, base_dir: str = "") -> dict:
    title = (game_node.attrib.get("name") or "").strip()

    def text(tag: str) -> str:
        node = game_node.find(tag)
        return clean_display_text((node.text or "").strip()) if node is not None else ""

    manufacturer = text("manufacturer")
    metadata = {
        "title": title,
        "description": resolve_game_description(text("description") or text("desc")),
        "developer": text("developer") or manufacturer,
        "publisher": text("publisher") or manufacturer,
        "genres": text("genre"),
    }
    year = _parse_release_year(text("year") or text("releasedate"))
    if year:
        metadata["release_year"] = year

    for tag, field in (
        ("image", "cover_path"),
        ("thumbnail", "cover_path"),
        ("box2dfront", "cover_path"),
        ("fanart", "fanart_path"),
        ("screenshot", "screenshot_path"),
        ("titleshot", "screenshot_path"),
        ("marquee", "logo_path"),
        ("wheel", "logo_path"),
        ("video", "video_path"),
    ):
        rel = (game_node.findtext(tag) or "").strip()
        if rel and base_dir and not metadata.get(field):
            metadata[field] = _resolve_path(base_dir, rel)

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
        root = _read_xml_root(gamelist_path)
        if root is None:
            _GAMELIST_CACHE[folder] = index
            return index
        for game_node in root.iter("game"):
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
        xbmc.log(f"[Games] gamelist.xml parse failed folder={folder}: {exc}", xbmc.LOGWARNING)

    _GAMELIST_CACHE[folder] = index
    return index


def _find_skraper_dat_file(folder: str, platform_id: str = "") -> str:
    if platform_id:
        for name in PLATFORM_DAT_FILES.get(platform_id, ()):
            path = os.path.join(folder, name)
            if xbmcvfs.exists(path):
                return path
        preferred = f"{platform_id}.dat"
        path = os.path.join(folder, preferred)
        if xbmcvfs.exists(path):
            return path
    for file_path in sorted(_list_files(folder), key=str.lower):
        if file_path.lower().endswith(".dat"):
            return file_path
    return ""


def _load_skraper_dat_index(folder: str, platform_id: str = "") -> dict[str, dict]:
    folder = folder.rstrip("/\\")
    cache_key = f"{folder}|{platform_id}"
    if cache_key in _SKRAPER_DAT_CACHE:
        return _SKRAPER_DAT_CACHE[cache_key]

    index: dict[str, dict] = {}
    dat_path = _find_skraper_dat_file(folder, platform_id)
    if not dat_path:
        _SKRAPER_DAT_CACHE[cache_key] = index
        return index

    try:
        root = _read_xml_root(dat_path)
        if root is None:
            _SKRAPER_DAT_CACHE[cache_key] = index
            return index
        for game_node in root.iter("game"):
            metadata = _skraper_game_to_metadata(game_node, folder)
            metadata["skraper_game_name"] = metadata.get("title") or ""
            title_key = _normalize_match_key(metadata.get("title") or "")
            if title_key:
                index[title_key] = dict(metadata)
            for rom_node in game_node.findall("rom"):
                rom_name = (rom_node.attrib.get("name") or "").strip()
                if not rom_name:
                    continue
                for key in _rom_lookup_keys(rom_name):
                    index[key] = dict(metadata)
        xbmc.log(
            f"[Games] loaded Skraper dat path={dat_path} entries={len(index)}",
            xbmc.LOGINFO,
        )
    except Exception as exc:
        xbmc.log(f"[Games] Skraper .dat parse failed path={dat_path}: {exc}", xbmc.LOGWARNING)

    _SKRAPER_DAT_CACHE[cache_key] = index
    return index


def find_source_folder(rom_path: str, source_folder: str = "") -> str:
    if source_folder and path_exists(source_folder):
        return source_folder.rstrip("/\\")
    rom = _norm_path(rom_path)
    parts = rom.split("/")
    for depth in range(len(parts) - 1, 0, -1):
        candidate = "/".join(parts[:depth])
        if _folder_has_local_metadata(candidate):
            return candidate
    parent = os.path.dirname(rom_path.replace("/", os.sep))
    return parent.rstrip("/\\") if parent else ""


def _lookup_dat_metadata(rom_path: str, *, source_folder: str = "", platform_id: str = "") -> dict:
    folders: list[str] = []
    if source_folder:
        folders.append(source_folder.rstrip("/\\"))
    discovered = find_source_folder(rom_path, source_folder)
    if discovered and discovered not in folders:
        folders.append(discovered)

    keys = _rom_lookup_keys(rom_path)
    stem_key = _normalize_match_key(_stem(rom_path))

    for folder in folders:
        index = _load_skraper_dat_index(folder, platform_id)
        for key in keys:
            if key in index:
                return dict(index[key])
        if stem_key and stem_key in index:
            return dict(index[stem_key])
        best_meta: dict | None = None
        best_score = 0
        for meta in index.values():
            score = _score_name_match(_stem(rom_path), meta.get("title") or "", meta.get("skraper_game_name") or "")
            if score > best_score:
                best_score = score
                best_meta = meta
        if best_meta and best_score >= 500:
            return dict(best_meta)
    return {}


def lookup_gamelist_metadata(rom_path: str, *, source_folder: str = "") -> dict:
    folder = find_source_folder(rom_path, source_folder)
    index = _load_gamelist_index(folder)
    for key in _rom_lookup_keys(rom_path):
        if key in index:
            return dict(index[key])

    rel_from_folder = _norm_path(rom_path)
    if folder and rel_from_folder.lower().startswith(_norm_path(folder).lower()):
        rel = rel_from_folder[len(_norm_path(folder)) :].lstrip("/").lower()
        if rel in index:
            return dict(index[rel])
    return {}


def lookup_skraper_dat_metadata(
    rom_path: str,
    *,
    source_folder: str = "",
    platform_id: str = "",
) -> dict:
    return _lookup_dat_metadata(rom_path, source_folder=source_folder, platform_id=platform_id)


def _stem(path: str) -> str:
    name = _basename_key(path)
    if "." in name:
        return name.rsplit(".", 1)[0]
    return name


def _first_existing(paths: list[str]) -> str:
    for path in paths:
        usable = usable_art_path(path)
        if usable:
            return usable
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


def _iter_image_files(folder: str, suffixes: set[str], *, max_depth: int = 4) -> list[str]:
    if not folder or max_depth < 0 or not path_exists(folder):
        return []
    found: list[str] = []
    for file_path in _list_files(folder):
        if Path(file_path).suffix.lower() in suffixes:
            found.append(file_path)
    if max_depth > 0:
        for name in _list_dirs(folder):
            found.extend(_iter_image_files(os.path.join(folder, name), suffixes, max_depth=max_depth - 1))
    return found


def _find_media_in_folder(folder: str, *needles: str, suffixes: set[str]) -> str:
    if not folder or not path_exists(folder):
        return ""
    needles_norm = [_normalize_match_key(needle) for needle in needles if needle]
    best_path = ""
    best_score = 0
    for file_path in _iter_image_files(folder, suffixes):
        stem_key = _normalize_match_key(Path(file_path).stem)
        for needle in needles_norm:
            if stem_key == needle:
                return normalize_art_path(file_path)
        score = _score_name_match(Path(file_path).stem, *needles)
        if score > best_score:
            best_score = score
            best_path = file_path
    if best_score >= 200:
        return normalize_art_path(best_path)
    return ""


def _discover_skraper_media(folder: str, game_name: str, rom_stem: str, *, rom_path: str = "") -> dict:
    if rom_path:
        found = _discover_skraper_media_by_name(folder, rom_path, game_name)
        if found:
            return found

    found: dict[str, str] = {}
    media_root = os.path.join(folder, "media")
    if not path_exists(media_root):
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

    skraper = _discover_skraper_media(folder, title_guess, stem, rom_path=rom_path)
    if skraper:
        xbmc.log(
            f"[Games] discovered local art rom={_basename_key(rom_path)} cover={skraper.get('cover_path', '')}",
            xbmc.LOGINFO,
        )
        return skraper

    media_roots = [folder, rom_dir]
    found: dict[str, str] = {}
    file_stems = _rom_file_stems(rom_path, game_name)
    normalized_stems = [_normalize_match_key(stem) for stem in file_stems if _normalize_match_key(stem)]
    name_variants = list(dict.fromkeys(file_stems + normalized_stems))

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
            for stem_name in file_stems:
                for suffix in suffixes:
                    candidates.append(os.path.join(rom_dir, f"{stem_name}{suffix}"))
                    candidates.append(os.path.join(rom_dir, f"{stem_name}-image{suffix}"))
        path = _first_existing(candidates)
        if path:
            found[field] = path
    return found


def lookup_local_metadata(
    rom_path: str,
    *,
    source_folder: str = "",
    platform_id: str = "",
) -> dict:
    metadata: dict = {}
    for chunk in (
        lookup_gamelist_metadata(rom_path, source_folder=source_folder),
        lookup_skraper_dat_metadata(rom_path, source_folder=source_folder, platform_id=platform_id),
    ):
        for key, value in chunk.items():
            if value and not metadata.get(key):
                metadata[key] = value

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
                if not path_exists(base):
                    continue
                for file_path in _iter_image_files(base, suffixes):
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
        if field.endswith("_path"):
            usable = usable_art_path(str(value))
            if not usable:
                continue
            updates[field] = usable
            continue
        if field == "description":
            updates[field] = resolve_game_description(str(value))
            if not updates[field]:
                continue
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
    platform_id: str = "",
    force: bool = False,
) -> tuple[str, str]:
    game = db.get_game(game_id)
    if not game:
        return "missing", "Game not found"
    if int(game.get("manual_metadata_locked") or 0) and not force:
        return "locked", "Manual metadata lock enabled"

    rom_path = game.get("rom_path") or ""
    if not source_folder and game.get("source_id"):
        source = db.one("SELECT folder_path FROM sources WHERE id=?", (game["source_id"],))
        if source and source.get("folder_path"):
            source_folder = source["folder_path"]
    if not platform_id:
        platform_id = game.get("platform_id") or ""

    metadata = lookup_local_metadata(
        rom_path,
        source_folder=source_folder,
        platform_id=platform_id,
    )
    has_content = any(
        metadata.get(key)
        for key in ("cover_path", "fanart_path", "screenshot_path", "video_path", "description")
    )
    if not has_content:
        return "no_match", "No local metadata found (check wii.dat and media/ next to your ROMs)"

    apply_local_metadata(db, game_id, metadata)
    return "ok", "Local metadata imported"
