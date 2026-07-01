from __future__ import annotations

import html
import re

IMPORT_PLACEHOLDER_RE = re.compile(r"^Imported from .+", re.IGNORECASE)
_WRAPPING_QUOTE_PAIRS = (
    ('"', '"'),
    ("'", "'"),
    ("\u201c", "\u201d"),
    ("\u2018", "\u2019"),
)


def is_import_placeholder_description(text: str) -> bool:
    return bool(IMPORT_PLACEHOLDER_RE.match((text or "").strip()))


def strip_wrapping_quotes(text: str) -> str:
    value = (text or "").strip()
    if len(value) < 2:
        return value
    for open_quote, close_quote in _WRAPPING_QUOTE_PAIRS:
        if value.startswith(open_quote) and value.endswith(close_quote):
            inner = value[len(open_quote) : -len(close_quote)].strip()
            if inner:
                return inner
    return value


def clean_display_text(text: str) -> str:
    value = html.unescape((text or "").strip())
    if not value:
        return ""

    if "Ã" in value or "â€™" in value or "â€œ" in value:
        try:
            value = value.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    value = value.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = strip_wrapping_quotes(value)
    return value.strip()


def resolve_game_description(*candidates: str) -> str:
    for raw in candidates:
        cleaned = clean_display_text(raw)
        if cleaned and not is_import_placeholder_description(cleaned):
            return cleaned
    return ""
