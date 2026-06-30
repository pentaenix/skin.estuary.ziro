from __future__ import annotations

from datetime import datetime

import xbmc

from ..paths import userdata_dir

LOG_TAG = "[Ziro Games SS]"
LOG_FILE = userdata_dir() / "ss.log"
MAX_LOG_BYTES = 512_000
CHUNK_SIZE = 900


def _rotate_if_needed() -> None:
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_BYTES:
            backup = LOG_FILE.with_suffix(".log.old")
            if backup.exists():
                backup.unlink()
            LOG_FILE.replace(backup)
    except OSError:
        pass


def _write_file(line: str) -> None:
    try:
        _rotate_if_needed()
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line)
            if not line.endswith("\n"):
                handle.write("\n")
    except OSError as exc:
        xbmc.log(f"{LOG_TAG} could not write ss.log: {exc}", xbmc.LOGWARNING)


def _emit_chunks(level: int, prefix: str, text: str) -> None:
    if not text:
        xbmc.log(prefix, level)
        return
    if len(text) <= CHUNK_SIZE:
        xbmc.log(f"{prefix} {text}", level)
        return
    xbmc.log(f"{prefix} ({len(text)} chars, split across lines)", level)
    for index, start in enumerate(range(0, len(text), CHUNK_SIZE), start=1):
        chunk = text[start : start + CHUNK_SIZE]
        xbmc.log(f"{prefix} [{index}] {chunk}", level)


def log_info(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_file(f"{stamp} INFO  {message}")
    _emit_chunks(xbmc.LOGINFO, LOG_TAG, message)


def log_warning(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_file(f"{stamp} WARN  {message}")
    _emit_chunks(xbmc.LOGWARNING, LOG_TAG, message)


def log_error(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_file(f"{stamp} ERROR {message}")
    _emit_chunks(xbmc.LOGERROR, LOG_TAG, message)


def log_http_error(status: int, url: str, body: str) -> str:
    detail = (body or "").strip()
    log_error(f"HTTP {status}")
    log_error(f"URL: {url}")
    if detail:
        log_error(f"BODY: {detail}")
    summary = f"ScreenScraper HTTP {status}"
    if detail:
        summary = f"{summary}: {detail[:300]}"
    return f"{summary}\nFull URL and body are in ss.log"
