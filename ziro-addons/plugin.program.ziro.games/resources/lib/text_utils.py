from __future__ import annotations

import html
import re
import unicodedata

IMPORT_PLACEHOLDER_RE = re.compile(r"^Imported from .+", re.IGNORECASE)
_WRAPPING_QUOTE_PAIRS = (
    ('"', '"'),
    ("'", "'"),
    ("\u201c", "\u201d"),
    ("\u2018", "\u2019"),
    ("\u00ab", "\u00bb"),
    ("\u2039", "\u203a"),
)
_EXPLICIT_EDGE_QUOTES = set(
    '"\'`´′″‛«»„“”‚‘’‹›「」『』'
)


def is_import_placeholder_description(text: str) -> bool:
    return bool(IMPORT_PLACEHOLDER_RE.match((text or "").strip()))


def _is_edge_quote_char(char: str) -> bool:
    if not char:
        return False
    if char in _EXPLICIT_EDGE_QUOTES:
        return True
    return unicodedata.category(char) in {"Pi", "Pf"}


def strip_edge_quotes(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    changed = True
    while changed and value:
        changed = False
        while value and _is_edge_quote_char(value[0]):
            value = value[1:].strip()
            changed = True
        while value and _is_edge_quote_char(value[-1]):
            value = value[:-1].strip()
            changed = True
    return value


def strip_wrapping_quotes(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    changed = True
    while changed and value:
        changed = False
        for open_quote, close_quote in _WRAPPING_QUOTE_PAIRS:
            if len(value) >= len(open_quote) + len(close_quote) and value.startswith(open_quote) and value.endswith(close_quote):
                inner = value[len(open_quote) : -len(close_quote)].strip()
                if inner != value:
                    value = inner
                    changed = True
        stripped = strip_edge_quotes(value)
        if stripped != value:
            value = stripped
            changed = True
    return value


def strip_decorative_quotes(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r'"{2,}', "", value)
    value = strip_wrapping_quotes(value)

    lines: list[str] = []
    for line in value.split("\n"):
        cleaned = strip_wrapping_quotes(strip_edge_quotes(line.strip()))
        lines.append(cleaned)
    value = "\n".join(lines)

    return strip_wrapping_quotes(strip_edge_quotes(value)).strip()


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
    value = strip_decorative_quotes(value)
    return value.strip()


def resolve_game_description(*candidates: str) -> str:
    for raw in candidates:
        cleaned = clean_display_text(raw)
        if cleaned and not is_import_placeholder_description(cleaned):
            return cleaned
    return ""
