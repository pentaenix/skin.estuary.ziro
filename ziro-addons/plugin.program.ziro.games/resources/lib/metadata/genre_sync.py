from __future__ import annotations

import re

GENRE_ALIASES: dict[str, tuple[str, ...]] = {
    "rpg": ("rpg", "role-playing", "role playing", "role playing game", "jrpg"),
    "platformer": ("platform", "platformer", "platform game"),
    "adventure": ("adventure", "action-adventure", "action adventure"),
    "racing": ("racing", "race", "driving"),
    "fighting": ("fighting", "fighter", "beat em up", "beat'em up", "brawler"),
    "coop": ("co-op", "coop", "cooperative", "co operative"),
}


def _normalize_genre_name(name: str) -> str:
    text = (name or "").strip().lower()
    text = re.sub(r"[^\w\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def map_genre_names_to_ids(genre_names: list[str]) -> list[str]:
    matched: list[str] = []
    for raw_name in genre_names:
        normalized = _normalize_genre_name(raw_name)
        if not normalized:
            continue
        for genre_id, aliases in GENRE_ALIASES.items():
            if any(alias in normalized or normalized in alias for alias in aliases):
                if genre_id not in matched:
                    matched.append(genre_id)
    return matched
