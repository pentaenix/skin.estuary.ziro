#!/usr/bin/env python3
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
ADDONS = ROOT / "ziro-addons"
DIST = ROOT / "dist"


def addon_version(addon_dir: Path) -> str:
    root = ET.parse(addon_dir / "addon.xml").getroot()
    return root.attrib["version"]


def zip_addon(addon_dir: Path) -> Path:
    version = addon_version(addon_dir)
    out = DIST / f"{addon_dir.name}-{version}.zip"
    with ZipFile(out, "w", ZIP_DEFLATED) as zf:
        for path in addon_dir.rglob("*"):
            if path.is_file():
                rel = path.relative_to(addon_dir.parent)
                if "__pycache__" in rel.parts or path.suffix == ".pyc":
                    continue
                zf.write(path, rel.as_posix())
    return out


def package_skin_snapshot() -> Path:
    # This packages the current repo root as a skin zip. Use after you have renamed addon.xml
    # to your fork id/name. It excludes dev-only folders.
    root_xml = ROOT / "addon.xml"
    if not root_xml.exists():
        raise RuntimeError("addon.xml not found at repo root")
    addon = ET.parse(root_xml).getroot()
    skin_id = addon.attrib.get("id", "skin.estuary.zirogames")
    version = addon.attrib.get("version", "0.0.0")
    out = DIST / f"{skin_id}-{version}.zip"
    excluded_top = {".git", "dist", "ziro-addons", "tools", "docs", "patch_ziro_games_initial_setup"}
    with ZipFile(out, "w", ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if rel.parts and rel.parts[0] in excluded_top:
                continue
            if "__pycache__" in rel.parts or path.suffix in {".pyc", ".bak"}:
                continue
            zf.write(path, f"{skin_id}/{rel.as_posix()}")
    return out


def main() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    for old in DIST.glob("*.zip"):
        old.unlink()
    for addon_dir in sorted(p for p in ADDONS.iterdir() if p.is_dir()):
        print(f"wrote {zip_addon(addon_dir)}")
    try:
        print(f"wrote {package_skin_snapshot()}")
    except Exception as exc:
        print(f"warn: skin package skipped: {exc}")


if __name__ == "__main__":
    main()
