from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmc

USER_AGENT = "ZiroGames/0.2 Kodi plugin.program.ziro.games"
DEFAULT_TIMEOUT = 25


def normalize_api_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def get_json(url: str, api_key: str, params: dict[str, Any] | None = None, retries: int = 3) -> dict[str, Any]:
    api_key = normalize_api_key(api_key)
    if params:
        url = f"{url}?{urlencode(params)}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("success", True):
                raise RuntimeError(payload.get("errors") or payload.get("message") or "SteamGridDB request failed")
            return payload
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            message = _http_error_message(exc.code, url, body)
            xbmc.log(f"[Ziro Games SGDB] {message}", xbmc.LOGERROR)
            last_error = RuntimeError(message)
            if exc.code == 429 and attempt < retries - 1:
                wait = 2 + attempt * 3
                xbmc.log(f"[Ziro Games SGDB] rate limited, sleeping {wait}s", xbmc.LOGWARNING)
                time.sleep(wait)
                continue
            raise last_error from exc
        except URLError as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(1)
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("SteamGridDB request failed")


def _http_error_message(status: int, url: str, body: str) -> str:
    detail = body.strip()
    if detail:
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                detail = str(parsed.get("errors") or parsed.get("message") or detail)
        except json.JSONDecodeError:
            detail = re.sub(r"\s+", " ", detail)[:240]
    return f"SteamGridDB HTTP {status} for {url}" + (f": {detail}" if detail else "")


def download_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
        return response.read()
