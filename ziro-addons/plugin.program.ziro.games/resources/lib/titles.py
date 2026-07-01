from __future__ import annotations

import re

from .scanner import SEPARATORS, TITLE_JUNK, clean_title, display_name

_SMALL_WORDS = frozenset({"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to", "vs"})


def clean_display_name(name: str) -> str:
    name = (name or "").strip()
    if "." in name:
        name = ".".join(name.split(".")[:-1]) or name
    title = SEPARATORS.sub(" ", name)
    title = TITLE_JUNK.sub(" ", title)
    return re.sub(r"\s+", " ", title).strip()


def title_case(text: str) -> str:
    words = text.split()
    if not words:
        return text
    result: list[str] = []
    for index, word in enumerate(words):
        lower = word.lower()
        if index > 0 and lower in _SMALL_WORDS:
            result.append(lower)
        elif word.isupper() and len(word) > 1:
            result.append(word)
        else:
            result.append(word.capitalize())
    return " ".join(result)


def display_title(title: str = "", *, rom_path: str = "") -> str:
    raw = (title or "").strip()
    rom_name = display_name(rom_path) if rom_path else ""
    if rom_path and (not raw or raw == rom_name):
        cleaned = clean_title(rom_path)
    else:
        cleaned = clean_display_name(raw)
        if not cleaned and rom_path:
            cleaned = clean_title(rom_path)
    if not cleaned:
        cleaned = raw or rom_name
    return title_case(cleaned) if cleaned else "Unknown"
