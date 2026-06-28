#!/usr/bin/env python3
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDONS = ROOT / "ziro-addons"


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


def main() -> None:
    if not ADDONS.exists():
        fail("ziro-addons/ not found. Did you apply the patch from the repo root?")
    problems: list[str] = []
    for addon in sorted(p for p in ADDONS.iterdir() if p.is_dir()):
        addon_xml = addon / "addon.xml"
        if not addon_xml.exists():
            problems.append(f"{addon.name}: missing addon.xml")
            continue
        try:
            root = ET.parse(addon_xml).getroot()
        except Exception as exc:
            problems.append(f"{addon.name}: invalid addon.xml: {exc}")
            continue
        addon_id = root.attrib.get("id")
        if addon_id != addon.name:
            problems.append(f"{addon.name}: addon id mismatch: {addon_id}")
        version = root.attrib.get("version")
        if not version:
            problems.append(f"{addon.name}: missing version")
        print(f"ok {addon.name} {version}")
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print("All Ziro add-on manifests validated.")


if __name__ == "__main__":
    main()
