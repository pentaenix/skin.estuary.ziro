# Estuary Ziro Games — Codex Handoff

This repository is a fork of Kodi's default Estuary skin plus a small Ziro Games add-on suite. The product goal is **not** a proof of concept and **not** a launcher shortcut. The goal is an effortless media-center experience where games feel like Movies/TV/Music in Kodi.

## Product goal

The final living-room flow should be:

```text
Power on Windows TV PC
→ Kodi opens directly
→ Estuary Ziro skin is active
→ Home menu shows Movies / TV Shows / Music / Games / Settings / Power
→ Highlight Games
→ Estuary-style rows appear:
   Continue Playing
   Recently Added
   Favorites
   Nintendo Wii
   Nintendo GameCube
   Game Boy Advance
   Super Nintendo
   Nintendo 64
   PlayStation
   RPG
   Platformer
   Racing
   Fighting
   Co-op
→ Move down to a row
→ Click one game cover
→ Correct emulator opens the game
→ Close emulator or press mapped Home
→ Kodi returns to the same Games view
```

The user likes Estuary and does **not** want a visual redesign. Keep Estuary's spacing, colors, typography, navigation behavior, and home-screen language. The user-facing difference should be: **Games are first-class media.**

## Current repository shape

This repo root is the forked skin itself:

```text
addon.xml                  # skin add-on manifest; id must be skin.estuary.ziro
xml/                       # Estuary XML skin files
media/, colors/, themes/   # Estuary visual assets
ziro-addons/               # companion game add-ons
  plugin.program.ziro.games/
  script.ziro.games.launcher/
  service.ziro.games/
tools/                     # validation/packaging/dev helpers
docs/                      # project documentation
dev_deploy_to_kodi.bat     # Windows dev deploy script for Mateo's TV PC
```

The root skin zip is packaged as `skin.estuary.ziro-<version>.zip`. It must install beside the stock Estuary skin, never replace it.

## Current implementation state

The project currently has the initial scaffolding:

- `skin.estuary.ziro` exists and can be deployed to Kodi.
- The existing Estuary `Games` home action has been redirected toward `plugin://plugin.program.ziro.games/home`.
- `plugin.program.ziro.games` owns the game-library UI and database.
- `script.ziro.games.launcher` is the intended launch bridge for emulator execution.
- `service.ziro.games` is reserved for focus/process/hotkey/session behavior.
- Dynamic game sources are being introduced so the user can add arbitrary platforms/consoles and folders without moving large libraries.

This is not finished. The most important next work is to convert the Games home experience from “open plugin menu” into **true Estuary-style home rows/widgets** powered by plugin routes.

## Hard product constraints

Do not violate these:

1. Do not replace Estuary visually.
2. Do not depend on Playnite as the visible frontend.
3. Do not depend on AEL/AKL for the final user-facing UX.
4. Do not force the user to move ROMs/games into hardcoded folders.
5. Do not require per-game manual shortcuts.
6. Do not hide games behind nested menus like `Games → Platform → List → Game` for normal use.
7. Do not block Kodi's UI while scanning, scraping, or launching.
8. Do not make the user install four zips after every pull. `dev_deploy_to_kodi.bat` is the dev loop.
9. Do not track generated `dist/*.zip` artifacts in git.
10. Do not assume the Windows user or drive letters except in local/dev convenience scripts.

## Desired architecture

### Skin layer: `skin.estuary.ziro`

The skin is responsible for visual integration only:

- Add a first-class Games home item.
- Show Estuary-style widget rows for games.
- Source those rows from `plugin.program.ziro.games` routes.
- Preserve all default Estuary settings like color/theme selection.
- Avoid hardcoding individual games in XML.

The skin should not scan ROM folders, launch emulators, or own metadata.

### Library/UI layer: `plugin.program.ziro.games`

The plugin owns:

- dynamic source/platform setup
- source scanning
- SQLite database
- metadata/artwork storage
- Kodi ListItems for rows, platforms, genres, and game entries
- routing for skin widgets
- user-facing library menus and diagnostic screens

Target plugin routes:

```text
plugin://plugin.program.ziro.games/home
plugin://plugin.program.ziro.games/continue
plugin://plugin.program.ziro.games/recent
plugin://plugin.program.ziro.games/favorites
plugin://plugin.program.ziro.games/platforms
plugin://plugin.program.ziro.games/platform/<platform_id>
plugin://plugin.program.ziro.games/genres
plugin://plugin.program.ziro.games/genre/<genre_id>
plugin://plugin.program.ziro.games/sources
plugin://plugin.program.ziro.games/add_source
plugin://plugin.program.ziro.games/scan
plugin://plugin.program.ziro.games/game/<game_id>
plugin://plugin.program.ziro.games/launch/<game_id>
```

For home widgets, every item in a row should be a launchable game item whenever possible. The normal path should be one click to play.

### Launch layer: `script.ziro.games.launcher`

The launcher owns:

- resolving game id → rom path + emulator profile
- command-line construction
- quoting Windows paths correctly
- launching the emulator non-blockingly
- reporting launch errors clearly through Kodi notifications and logs
- updating play history where appropriate

Example launch profiles:

```text
Dolphin Wii/GameCube:
  executable: C:\Emulation\Emulators\Dolphin\Dolphin.exe
  args: -b -e "{rom_path}"

mGBA:
  executable: C:\Emulation\Emulators\mGBA\mGBA.exe
  args: -f "{rom_path}"

RetroArch:
  executable: C:\Emulation\Emulators\RetroArch\retroarch.exe
  args: -L "{core_path}" "{rom_path}"
```

### Service layer: `service.ziro.games`

The service should eventually own:

- emulator process watching
- session duration tracking
- return focus to Kodi after emulator exit
- optional Windows-specific focus helper integration
- optional air-mouse Home behavior

The preferred behavior is:

```text
Game launched from Kodi
→ emulator opens fullscreen
→ emulator exits or Home action triggers close/focus
→ Kodi returns focused to the Games view
```

## Development workflow

### macOS development

The user often edits on macOS, commits, then pulls on the Windows TV PC.

Run these on macOS before committing:

```bash
python3 tools/ziro_validate_addons.py
python3 tools/ziro_package_addons.py
```

Do not commit generated zips unless explicitly asked.

### Windows TV PC deployment

On the Windows Kodi PC, run from the repo root:

```bat
dev_deploy_to_kodi.bat
```

The script **pulls the current branch from origin first** (`git pull --ff-only`), then validates, packages, copies the skin and companion add-ons to Kodi, and restarts Kodi. No separate `git pull` step is needed before testing.

```text
C:\Users\Mateo\AppData\Roaming\Kodi\addons
```

### Agent / dev workflow

After finishing a change on any machine, **commit and push to the current branch** so the Windows deploy script can pick it up on the next run.

## Immediate next task for Codex

Implement production-safe home-row integration:

1. Locate how this Estuary version builds Movies/TV/Music home widgets.
2. Add equivalent Games widgets using routes from `plugin.program.ziro.games`.
3. Keep all styling/includes consistent with stock Estuary.
4. Do not introduce a custom-looking home screen.
5. Make Games rows show directly when Games is highlighted.
6. Rows should include at least:
   - Continue Playing
   - Recently Added
   - Favorites
   - one row per user-created platform/console when possible
   - one row per genre when possible
7. Provide safe fallback rows when the game database is empty:
   - Add Game Source
   - Scan / Refresh Library
   - Settings

## Second next task for Codex

Harden dynamic sources and scanning:

1. Let the user create arbitrary platforms/consoles.
2. Let the user choose any directory via Kodi's folder browser.
3. Let the user enter/edit extensions per source.
4. Store sources in SQLite.
5. Scan recursively.
6. Log skipped files with reasons.
7. Expose a diagnostic screen showing:
   - source folder
   - recursive yes/no
   - extension list
   - number of files seen
   - number accepted
   - number inserted
   - first 20 skipped files + reason
8. Make rescans idempotent and preserve manual edits.

## Third next task for Codex

Harden launching:

1. Ensure real Wii/GameCube/GBA games launch from game items.
2. Make launch failures explicit.
3. Add logging around resolved emulator path, rom path, cwd, arguments, and process id.
4. Ensure paths with spaces work.
5. Keep Kodi responsive.
6. Return focus to Kodi after emulator exit where feasible.

## Definition of success for the next production milestone

The milestone is good when:

```text
1. User can deploy with dev_deploy_to_kodi.bat.
2. Kodi starts with Estuary Ziro active.
3. User highlights Games on the Kodi home screen.
4. Rows appear immediately without entering plugin submenus.
5. User can add a new game source from Kodi without moving files.
6. At least one Wii or GBA game appears in a Games row.
7. One click launches the configured emulator.
8. Closing the emulator returns to Kodi.
9. Estuary color/theme settings still work.
```

## Be careful with generated files

The repository should track source and docs. It should not track:

```text
dist/
*.zip
*.bak
__pycache__/
.ziro_games_*_manifest.json
.ziro_games_patch_state.json
```

If `.gitignore` blocks Python files with `*.py`, add explicit exceptions for this project’s source folders.
