from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmc

from .sgdb_log import log_error, log_http_error, log_info

USER_AGENT = "ZiroGames/0.2 Kodi plugin.program.ziro.games"
DEFAULT_TIMEOUT = 25


def normalize_api_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def get_json(url: str, api_key: str, params: dict[str, Any] | None = None, retries: int = 3) -> dict[str, Any]:
    api_key = normalize_api_key(api_key)
    request_url = url
    if params:
        request_url = f"{url}?{urlencode(params)}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            log_info(f"GET {request_url}")
            request = Request(request_url, headers=headers)
            with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("success", True):
                detail = str(payload.get("errors") or payload.get("message") or "SteamGridDB request failed")
                log_error(f"success=false url={request_url} detail={detail}")
                raise RuntimeError(f"SteamGridDB error: {detail}")
            return payload
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            message = log_http_error(exc.code, request_url, body)
            last_error = RuntimeError(message)
            if exc.code == 429 and attempt < retries - 1:
                wait = 2 + attempt * 3
                log_error(f"rate limited, sleeping {wait}s")
                time.sleep(wait)
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
    raise RuntimeError("SteamGridDB request failed")


def download_bytes(url: str) -> bytes:
    log_info(f"DOWNLOAD {url}")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
        return response.read()
