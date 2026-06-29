from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .http_client import get_json, normalize_api_key
from .matcher import pick_best_match
from .sgdb_log import log_warning

API_BASE = "https://www.steamgriddb.com/api/v2"


def validate_api_key(api_key: str) -> bool:
    api_key = normalize_api_key(api_key)
    if not api_key:
        return False
    try:
        get_json(f"{API_BASE}/search/autocomplete/test", api_key)
        return True
    except Exception as exc:
        log_warning(f"API key validation failed: {exc}")
        return False


def search_game(title: str, api_key: str) -> dict | None:
    query = title.strip()
    if not query:
        return None
    encoded = quote(query, safe="")
    payload = get_json(f"{API_BASE}/search/autocomplete/{encoded}", api_key)
    results = payload.get("data") or []
    if not isinstance(results, list):
        return None
    return pick_best_match(title, results)


def _pick_asset(assets: list[dict]) -> dict | None:
    if not assets:
        return None
    safe = [item for item in assets if not item.get("nsfw")]
    pool = safe or assets
    pool.sort(key=lambda item: int(item.get("score") or 0), reverse=True)
    return pool[0]


def _assets(url: str, api_key: str, params: dict[str, Any] | None = None) -> list[dict]:
    try:
        payload = get_json(url, api_key, params=params)
    except RuntimeError:
        return []
    data = payload.get("data") or []
    return data if isinstance(data, list) else []


def fetch_grid(sgdb_game_id: int, api_key: str) -> dict | None:
    attempts = [
        {
            "dimensions": "600x900",
            "types": "static",
            "styles": "alternate,material,blurred,no_logo",
            "mimes": "image/png,image/jpeg,image/webp",
        },
        {"dimensions": "600x900", "types": "static"},
        None,
    ]
    for params in attempts:
        assets = _assets(f"{API_BASE}/grids/game/{sgdb_game_id}", api_key, params)
        picked = _pick_asset(assets)
        if picked:
            return picked
    return None


def fetch_hero(sgdb_game_id: int, api_key: str) -> dict | None:
    attempts = [
        {
            "types": "static",
            "styles": "alternate,material,blurred",
            "mimes": "image/png,image/jpeg,image/webp",
        },
        {"types": "static"},
        None,
    ]
    for params in attempts:
        assets = _assets(f"{API_BASE}/heroes/game/{sgdb_game_id}", api_key, params)
        picked = _pick_asset(assets)
        if picked:
            return picked
    return None


def fetch_logo(sgdb_game_id: int, api_key: str) -> dict | None:
    # Logo styles: official, white, black, custom only (not "alternate").
    attempts = [
        {
            "types": "static",
            "styles": "official,white,black,custom",
            "mimes": "image/png,image/webp",
        },
        {"types": "static"},
        None,
    ]
    for params in attempts:
        assets = _assets(f"{API_BASE}/logos/game/{sgdb_game_id}", api_key, params)
        picked = _pick_asset(assets)
        if picked:
            return picked
    return None
