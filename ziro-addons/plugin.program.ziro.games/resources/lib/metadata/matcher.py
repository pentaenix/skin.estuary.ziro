from __future__ import annotations

import re
from difflib import SequenceMatcher


def normalize_title(title: str) -> str:
    text = (title or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def pick_best_match(query: str, results: list[dict], min_score: float = 0.58) -> dict | None:
    if not results:
        return None
    query_norm = normalize_title(query)
    if not query_norm:
        return None

    scored: list[tuple[float, dict]] = []
    for item in results:
        name = item.get("name") or ""
        name_norm = normalize_title(name)
        if not name_norm:
            continue
        score = SequenceMatcher(None, query_norm, name_norm).ratio()
        if query_norm in name_norm or name_norm in query_norm:
            score += 0.08
        if item.get("verified"):
            score += 0.04
        scored.append((score, item))

    if not scored:
        return None

    scored.sort(key=lambda pair: pair[0], reverse=True)
    best_score, best = scored[0]
    if best_score < min_score:
        return None
    return best
