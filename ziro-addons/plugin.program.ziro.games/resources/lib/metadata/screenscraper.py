from __future__ import annotations

import hashlib
import json
import re
import time
import zlib
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmc
import xbmcaddon
import xbmcvfs

from .ss_log import log_error, log_http_error, log_info, log_warning
from .ss_systems import screenscraper_system_id

API_BASE = "https://api.screenscraper.fr/api2"
SOFT_NAME = "ZiroGames"
USER_AGENT = "ZiroGames/0.3 plugin.program.ziro.games"
DEFAULT_TIMEOUT = 30
MAX_HASH_BYTES = 120 * 1024 * 1024
REGION_PRIORITY = ("wor", "ss", "eu", "us", "fr", "jp", "en")
ADDON = xbmcaddon.Addon("plugin.program.ziro.games")


def _setting(key: str) -> str:
    return (ADDON.getSetting(key) or "").strip()


def credentials_configured() -> bool:
    return all(
        _setting(key)
        for key in (
            "screenscraper_user",
            "screenscraper_password",
            "screenscraper_dev_id",
            "screenscraper_dev_password",
        )
    )


def _base_params() -> dict[str, str]:
    params = {
        "devid": _setting("screenscraper_dev_id"),
        "devpassword": _setting("screenscraper_dev_password"),
        "softname": SOFT_NAME,
        "ssid": _setting("screenscraper_user"),
        "sspassword": _setting("screenscraper_password"),
        "output": "json",
    }
    missing = [key for key, value in params.items() if key in {"devid", "devpassword", "ssid", "sspassword"} and not value]
    if missing:
        raise RuntimeError(
            "ScreenScraper credentials are incomplete. "
            "Set username, password, developer id, and developer password in Games settings."
        )
    return params


def _request(endpoint: str, params: dict[str, Any], *, retries: int = 3) -> dict[str, Any]:
    query = {**_base_params(), **params}
    request_url = f"{API_BASE}/{endpoint}?{urlencode(query)}"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            log_info(f"GET {request_url}")
            request = Request(request_url, headers=headers)
            with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            response_body = payload.get("response") or {}
            if response_body.get("error"):
                raise RuntimeError(str(response_body.get("error")))
            return payload
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            message = log_http_error(exc.code, request_url, body)
            last_error = RuntimeError(message)
            if exc.code in {429, 430, 503} and attempt < retries - 1:
                time.sleep(2 + attempt * 3)
                continue
            raise last_error from exc
        except URLError as exc:
            last_error = exc
            log_error(f"network error url={request_url}: {exc}")
            if attempt < retries - 1:
                time.sleep(1)
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("ScreenScraper request failed")


def validate_credentials() -> bool:
    if not credentials_configured():
        return False
    try:
        _request("ssuserInfos.php", {})
        return True
    except Exception as exc:
        log_warning(f"credential validation failed: {exc}")
        return False


def _response_data(payload: dict[str, Any]) -> dict[str, Any]:
    response = payload.get("response") or {}
    jeu = response.get("jeu")
    if isinstance(jeu, dict):
        return jeu
    jeux = response.get("jeux")
    if isinstance(jeux, list) and jeux:
        first = jeux[0]
        return first if isinstance(first, dict) else {}
    if isinstance(jeux, dict):
        for value in jeux.values():
            if isinstance(value, dict):
                return value
    return {}


def _normalize_region(region: str) -> str:
    return (region or "").strip().lower().replace("_", "-")


def _iter_media_entries(medias: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if isinstance(medias, list):
        entries.extend(item for item in medias if isinstance(item, dict))
        return entries
    if not isinstance(medias, dict):
        return entries
    for key, value in medias.items():
        key_lower = str(key).lower()
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    item = dict(item)
                    item.setdefault("type", key_lower)
                    entries.append(item)
        elif isinstance(value, dict):
            for region, item in value.items():
                if isinstance(item, dict):
                    merged = dict(item)
                    merged.setdefault("type", key_lower)
                    merged.setdefault("region", region)
                    entries.append(merged)
                elif isinstance(item, str) and item.startswith("http"):
                    entries.append({"type": key_lower, "region": region, "url": item})
    return entries


def _media_type(entry: dict[str, Any]) -> str:
    for key in ("type", "media", "format"):
        value = str(entry.get(key) or "").lower()
        if value:
            return value
    return ""


def _media_url(entry: dict[str, Any]) -> str:
    for key in ("url", "media_url"):
        value = entry.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return ""


def _pick_media(jeu: dict[str, Any], *needles: str) -> str:
    entries = _iter_media_entries(jeu.get("medias"))
    needles_lower = tuple(needle.lower() for needle in needles)
    matches = [
        entry for entry in entries
        if any(needle in _media_type(entry) for needle in needles_lower)
    ]
    if not matches:
        return ""
    for region in REGION_PRIORITY:
        for entry in matches:
            if _normalize_region(str(entry.get("region") or "")) == region:
                url = _media_url(entry)
                if url:
                    return url
    for entry in matches:
        url = _media_url(entry)
        if url:
            return url
    return ""


def _rom_type(path: str) -> str:
    lower = path.lower()
    if lower.endswith((".iso", ".gdi", ".cue", ".chd", ".nrg", ".mds")):
        return "iso"
    return "rom"


def _file_size(path: str) -> int:
    try:
        stat = xbmcvfs.Stat(path)
        return int(stat.st_size())
    except Exception:
        try:
            return Path(path).stat().st_size
        except Exception:
            return 0


def _read_bytes(path: str) -> bytes:
    if xbmcvfs.exists(path):
        handle = xbmcvfs.File(path)
        try:
            data = handle.readBytes()
            if isinstance(data, bytes):
                return data
            if isinstance(data, bytearray):
                return bytes(data)
            if isinstance(data, str):
                return data.encode("latin-1", errors="ignore")
        finally:
            handle.close()
    with open(path, "rb") as handle:
        return handle.read()


def _rom_hashes(path: str) -> dict[str, str]:
    size = _file_size(path)
    if not size or size > MAX_HASH_BYTES:
        return {}
    data = _read_bytes(path)
    if not data:
        return {}
    return {
        "crc": f"{zlib.crc32(data) & 0xFFFFFFFF:08X}",
        "md5": hashlib.md5(data).hexdigest().upper(),
        "sha1": hashlib.sha1(data).hexdigest().upper(),
        "romtaille": str(size),
    }


def _clean_title(title: str) -> str:
    text = re.sub(r"\s*[\(\[].*?[\)\]]\s*", " ", title or "")
    text = re.sub(r"[._]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _response_games(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = payload.get("response") or {}
    jeux = response.get("jeux")
    games: list[dict[str, Any]] = []
    if isinstance(jeux, list):
        games.extend(item for item in jeux if isinstance(item, dict))
    elif isinstance(jeux, dict):
        games.extend(item for item in jeux.values() if isinstance(item, dict))
    if games:
        return games
    jeu = response.get("jeu")
    return [jeu] if isinstance(jeu, dict) else []


def search_games(platform_id: str, title: str, *, limit: int = 30) -> list[dict[str, Any]]:
    system_id = screenscraper_system_id(platform_id)
    if not system_id:
        return []
    query = _clean_title(title)
    if not query:
        return []
    payload = _request(
        "jeuRecherche.php",
        {"systemeid": str(system_id), "recherche": query},
    )
    return _response_games(payload)[:limit]


def lookup_game(
    *,
    platform_id: str,
    title: str,
    rom_path: str = "",
    ss_game_id: int | None = None,
) -> dict[str, Any] | None:
    system_id = screenscraper_system_id(platform_id)
    if not system_id:
        raise RuntimeError(f"No ScreenScraper system mapping for platform '{platform_id}'")

    if ss_game_id:
        payload = _request(
            "jeuInfos.php",
            {"systemeid": str(system_id), "gameid": str(ss_game_id), "romtype": "rom"},
        )
        jeu = _response_data(payload)
        if jeu:
            return jeu

    if rom_path and xbmcvfs.exists(rom_path):
        hashes = _rom_hashes(rom_path)
        if hashes:
            params = {
                "systemeid": str(system_id),
                "romtype": _rom_type(rom_path),
                "romnom": Path(rom_path).name,
                **hashes,
            }
            payload = _request("jeuInfos.php", params)
            jeu = _response_data(payload)
            if jeu:
                return jeu

    query = _clean_title(title)
    if not query:
        return None
    payload = _request(
        "jeuRecherche.php",
        {"systemeid": str(system_id), "recherche": query},
    )
    return _response_data(payload)


def extract_art_urls(jeu: dict[str, Any]) -> dict[str, str]:
    return {
        "cover": _pick_media(jeu, "box-2d", "boitiers_2d", "box2d"),
        "fanart": _pick_media(jeu, "fanart"),
        "logo": _pick_media(jeu, "wheel", "wheel-hd", "marquee"),
        "screenshot": _pick_media(jeu, "ss", "screenshot"),
        "video": _pick_media(jeu, "video", "media_video"),
    }


def list_media_urls(jeu: dict[str, Any], *needles: str) -> list[tuple[str, str]]:
    entries = _iter_media_entries(jeu.get("medias"))
    needles_lower = tuple(needle.lower() for needle in needles)
    matches = [
        entry for entry in entries
        if any(needle in _media_type(entry) for needle in needles_lower)
    ]
    options: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entry in matches:
        url = _media_url(entry)
        if not url or url in seen:
            continue
        seen.add(url)
        media_type = _media_type(entry) or "image"
        region = _normalize_region(str(entry.get("region") or "")) or "world"
        options.append((f"{region.upper()} · {media_type}", url))
    return options


def extract_metadata(jeu: dict[str, Any]) -> dict[str, Any]:
    game_id = jeu.get("id")
    noms = jeu.get("noms") or {}
    title = ""
    if isinstance(noms, dict):
        for region in REGION_PRIORITY:
            title = str(noms.get(f"nom_{region}") or noms.get(region) or "").strip()
            if title:
                break
        title = title or str(noms.get("nom_world") or noms.get("nom_eu") or noms.get("nom_us") or "").strip()
    synopsis = jeu.get("synopsis") or {}
    description = ""
    if isinstance(synopsis, dict):
        for region in REGION_PRIORITY:
            description = str(synopsis.get(f"synopsis_{region}") or synopsis.get(region) or "").strip()
            if description:
                break
    dates = jeu.get("dates") or {}
    release_year = 0
    if isinstance(dates, dict):
        for region in REGION_PRIORITY:
            raw = str(dates.get(f"date_{region}") or dates.get(region) or "")
            match = re.match(r"(\d{4})", raw)
            if match:
                release_year = int(match.group(1))
                break
    genres: list[str] = []
    raw_genres = jeu.get("genres")
    if isinstance(raw_genres, list):
        for item in raw_genres:
            if isinstance(item, dict):
                name = str(item.get("nom_eu") or item.get("noms", {}).get("nom_eu") or item.get("nom") or "").strip()
                if name:
                    genres.append(name)
    return {
        "ss_game_id": int(game_id) if game_id else None,
        "title": title,
        "description": description,
        "release_year": release_year,
        "developer": str(jeu.get("developpeur") or "").strip(),
        "publisher": str(jeu.get("editeur") or "").strip(),
        "genres": ", ".join(genres),
        "genre_names": genres,
    }


def fetch_system_logo(platform_id: str) -> str:
    system_id = screenscraper_system_id(platform_id)
    if not system_id:
        return ""
    payload = _request("systemesListe.php", {})
    systems = (payload.get("response") or {}).get("systemes") or []
    if isinstance(systems, dict):
        systems = list(systems.values())
    for system in systems:
        if not isinstance(system, dict):
            continue
        if int(system.get("id") or 0) != system_id:
            continue
        medias = system.get("medias") or {}
        for entry in _iter_media_entries(medias):
            media_type = _media_type(entry)
            if "logo" in media_type or "wheel" in media_type or "icon" in media_type:
                url = _media_url(entry)
                if url:
                    return url
        for key in ("media_logo", "media_logo_monochrome", "media_pictomonochrome"):
            value = medias.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
            if isinstance(value, dict):
                for item in value.values():
                    if isinstance(item, str) and item.startswith("http"):
                        return item
                    if isinstance(item, dict):
                        url = _media_url(item)
                        if url:
                            return url
    return ""
