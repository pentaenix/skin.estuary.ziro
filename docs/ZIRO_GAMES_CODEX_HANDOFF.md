# Ziro Games Codex Handoff

This document is for the next coding agent working in this repository. Treat this as a production Kodi project.

## The user's north star

The user wants an appliance-like Kodi media center:

```text
Movies / Series / Music / Games
```

The user should be able to highlight **Games**, move down into Estuary-style rows, select a cover, and play. Games should feel like movies, not like a plugin browser.

## What not to build

Do not build:

- a proof of concept
- a single hardcoded launcher
- a Playnite doorway as the final UI
- AEL/AKL-style nested launcher menus
- a custom skin that looks different from Estuary
- a system that forces the user to move files into specific folders
- a system that requires manually creating a shortcut per game

## What to build

Build a Kodi-native game library with these layers:

1. `skin.estuary.ziro` — Estuary visual integration.
2. `plugin.program.ziro.games` — game library, scanner, metadata, routes, ListItems.
3. `script.ziro.games.launcher` — game/emulator launch execution.
4. `service.ziro.games` — process/focus/session monitoring.
5. `dev_deploy_to_kodi.bat` — fast Windows TV-PC deploy.

## Repository map

```text
./addon.xml
  Skin manifest. Must use id="skin.estuary.ziro".

./xml/Home.xml and related includes
  The Games home action and widgets live here or in included XML.
  Keep the layout visually consistent with stock Estuary.

./ziro-addons/plugin.program.ziro.games/main.py
  Kodi plugin entrypoint. Routes plugin URLs.

./ziro-addons/plugin.program.ziro.games/resources/lib/db.py
  SQLite schema and data access. Add migrations here.

./ziro-addons/plugin.program.ziro.games/resources/lib/scanner.py
  Source scanning and file-extension matching. This must be dynamic.

./ziro-addons/plugin.program.ziro.games/resources/lib/routes.py
  Kodi ListItem construction and route rendering.

./ziro-addons/plugin.program.ziro.games/resources/settings.xml
  Plugin settings. Do not overload settings for large dynamic source state;
  use SQLite/userdata for that.

./ziro-addons/script.ziro.games.launcher/default.py
  Launch bridge. Must be robust with Windows paths and spaces.

./ziro-addons/service.ziro.games/service.py
  Future session watcher/focus-restoration service.

./tools/ziro_validate_addons.py
  Validates addon.xml files.

./tools/ziro_package_addons.py
  Creates installable zips under dist/.

./dev_deploy_to_kodi.bat
  Windows deploy script. This is the user's fast iteration path.
```

## How Kodi should use plugin routes

The plugin must expose stable content routes for the skin:

```text
/home
/continue
/recent
/favorites
/platforms
/platform/<platform_id>
/genres
/genre/<genre_id>
/sources
/add_source
/scan
/game/<game_id>
/launch/<game_id>
```

The skin should not query the SQLite database directly. The skin should use plugin paths.

## How rows should work

The desired Games home rows are:

```text
Continue Playing
Recently Added
Favorites
<Dynamic platform rows>
<Dynamic genre rows>
Sources / Setup fallback rows when empty
```

For dynamic platform rows, the plugin should generate a home route containing directory items or expose platform routes that the skin can point widgets at. If Kodi/Estuary XML cannot enumerate dynamic row definitions directly, implement the closest maintainable design:

- a fixed set of widget containers that point at plugin routes which return mixed row content; or
- a generated skin include file at deploy/build time; or
- a plugin home view styled as close to Estuary widgets as possible until the skin layer is fully patched.

Document whichever constraint is discovered. Do not hide the limitation.

## Dynamic source model

Sources are user-created. A source must store:

```text
name
platform display name
platform short name
folder path
recursive yes/no
extensions
emulator profile
scan stats
created/updated timestamps
```

The user must be able to choose the folder through Kodi's folder browser. Never require moving files.

## Scanner expectations

The scanner should:

- scan recursively when requested
- support arbitrary extensions per source
- normalize extension case
- skip hidden/system junk
- insert/update games idempotently
- preserve manual edits on rescan
- emit clear logs and user notifications
- provide diagnostics when 0 games are found

A failed scan with `0 games` must say why, such as:

```text
folder missing
no files seen
files seen but extensions did not match
source disabled
database write failed
```

## Launch expectations

A launchable game item must know:

```text
game_id
rom_path
emulator_profile_id
executable_path
arguments_template
working_directory
process_name
```

The launcher should replace tokens like:

```text
{rom_path}
{rom_dir}
{rom_name}
{core_path}
```

and quote safely on Windows.

## Logging expectations

Use Kodi logs generously with a clear prefix:

```text
[Ziro Games]
[Ziro Games Scanner]
[Ziro Games Launcher]
[Ziro Games Service]
```

When something fails, log enough for the user to paste a useful block back into ChatGPT/Codex.

## Compatibility notes

The current target is Windows Kodi on Mateo's TV PC. The user develops on macOS too. Keep code cross-platform where reasonable, but prioritize Windows behavior for launch/focus.

Skin dependency versions must match the installed Kodi. If `xbmc.gui` mismatch happens, use the target Kodi's `C:\Program Files\Kodi\addons\xbmc.gui\addon.xml` version or base the fork on the installed Estuary.

## Acceptance tests

Run these after changes:

```bash
python3 tools/ziro_validate_addons.py
python3 tools/ziro_package_addons.py
```

On Windows:

```bat
dev_deploy_to_kodi.bat
```

Then in Kodi:

```text
1. Estuary Ziro appears and is selectable.
2. Estuary color/theme settings still work.
3. Games opens the Ziro game experience.
4. A user-created Wii or GBA source scans at least one game.
5. The game appears in a row/list.
6. Clicking it launches the emulator.
7. Closing the emulator returns focus to Kodi or at least leaves Kodi running behind it.
```
