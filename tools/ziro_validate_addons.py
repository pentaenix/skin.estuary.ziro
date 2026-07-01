#!/usr/bin/env python3
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDONS = ROOT / "ziro-addons"
HOME_XML = ROOT / "xml" / "Home.xml"
GAMES_HOME_INCLUDES = ROOT / "xml" / "Includes_Ziro_Games_Home.xml"


def validate_games_home_layout() -> list[str]:
    problems: list[str] = []
    if not HOME_XML.exists():
        return ["xml/Home.xml not found"]
    home = HOME_XML.read_text(encoding="utf-8")
    if 'id="17001"' not in home:
        problems.append("Games home grouplist 17001 missing from xml/Home.xml")
    if 'list_id" value="17290"' not in home or "WidgetListCategories" not in home:
        problems.append(
            "Games home must include WidgetListCategories (list_id 17290) for the library options banner"
        )
    if "ZiroGamesGenreWidgets" in home:
        problems.append("Do not add ZiroGamesGenreWidgets to Home.xml without an explicit request")
    if GAMES_HOME_INCLUDES.exists():
        includes = GAMES_HOME_INCLUDES.read_text(encoding="utf-8")
        if '<include name="ZiroGamesWidgetList' in includes:
            for name in (
                "ZiroGamesWidgetListPoster",
                "ZiroGamesWidgetListBoxArt",
                "ZiroGamesWidgetListCaseArt",
            ):
                marker = f'<include name="{name}">'
                start = includes.find(marker)
                if start < 0:
                    continue
                end = includes.find("</include>", start)
                block = includes[start:end] if end > start else ""
                if '<control type="group">' in block.split("<definition>")[-1].split(
                    "<include content=\"CategoryLabel\">"
                )[0]:
                    problems.append(
                        f"{name}: do not wrap widget header/spinner/panel in a group control"
                    )
    return problems


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
    problems.extend(validate_games_home_layout())
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print("All Ziro add-on manifests validated.")


if __name__ == "__main__":
    main()
