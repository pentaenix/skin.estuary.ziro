# Ziro Games Initial Setup Patch

This patch adds the initial production scaffolding for a Kodi-native game center inside an Estuary fork.

It does three things:

1. Adds `ziro-addons/` with the game library plugin, launcher script, and session service.
2. Adds `tools/` scripts to validate and package Kodi-installable zips.
3. Patches `xml/Home.xml` when possible so Estuary's existing Games menu item opens `plugin.program.ziro.games`.

This is not the final game-wall UI. It is the foundation that lets us start iterating the skin against real plugin routes instead of AEL/Playnite menus.

After applying:

```bash
python3 tools/ziro_validate_addons.py
python3 tools/ziro_package_addons.py
```

Then install the generated add-on zips from `dist/` inside Kodi.
