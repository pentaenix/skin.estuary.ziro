from __future__ import annotations

import re

ROM_NOISE = re.compile(
    r"\b(usa|us|eur|europe|eu|japan|jpn|world|rev\s*\d+|revision|proto|demo|"
    r"beta|final|unl|unlicensed|hack|translation|fixed|v\d+(?:\.\d+)*)\b",
    re.IGNORECASE,
)
PAREN_BLOCK = re.compile(r"\([^)]*\)")
BRACKET_BLOCK = re.compile(r"\[[^\]]*\]")
SEPARATORS = re.compile(r"[._]+")


def _clean(text: str) -> str:
    text = PAREN_BLOCK.sub(" ", text)
    text = BRACKET_BLOCK.sub(" ", text)
    text = SEPARATORS.sub(" ", text)
    text = ROM_NOISE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text


def search_candidates(title: str) -> list[str]:
    raw = (title or "").strip()
    if not raw:
        return []

    seen: set[str] = set()
    ordered: list[str] = []

    def add(value: str) -> None:
        value = value.strip()
        if not value:
            return
        key = value.casefold()
        if key in seen:
            return
        seen.add(key)
        ordered.append(value)

    add(raw)
    add(_clean(raw))
    no_the = re.sub(r"^the\s+", "", _clean(raw), flags=re.IGNORECASE).strip()
    add(no_the)
    if "," in raw:
        add(raw.split(",", 1)[0].strip())
    if " - " in raw:
        add(raw.split(" - ", 1)[0].strip())
    return ordered
