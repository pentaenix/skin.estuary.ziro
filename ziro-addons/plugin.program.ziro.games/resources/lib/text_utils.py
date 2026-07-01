from __future__ import annotations

import html
import re


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
    return value.strip()
