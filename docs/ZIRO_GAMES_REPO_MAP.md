# Ziro Games Repository Map

This repo is intentionally split into a skin and companion add-ons.

## Root skin fork

The root directory is a Kodi skin add-on. Its `addon.xml` should identify it as:

```xml
<addon id="skin.estuary.ziro" name="Estuary Ziro" ...>
```

Important root folders:

```text
xml/       Estuary skin XML files
media/     skin media assets
colors/    Estuary color schemes
themes/    Estuary themes
language/  localization
```

The skin should remain visually Estuary. All game-specific data should come from plugin routes.

## Companion add-ons

### `ziro-addons/plugin.program.ziro.games`

Owns the game library.

Use it for:

- sources
- platforms
- scanner
- SQLite database
- metadata
- artwork paths
- Kodi ListItems
- plugin routes

Do not put emulator process management in the skin.

### `ziro-addons/script.ziro.games.launcher`

Owns emulator launching.

Use it for:

- command construction
- quoting
- subprocess launch
- launch errors
- play history updates

### `ziro-addons/service.ziro.games`

Owns background behavior.

Use it for:

- process watching
- session time
- return-to-Kodi focus
- hotkey/home-button integrations

## Tools

### `tools/ziro_validate_addons.py`

Checks add-on manifests before packaging/deploying.

### `tools/ziro_package_addons.py`

Builds installable zips under `dist/`.

### `tools/ziro_print_kodi_paths.py`

Helps diagnose local Kodi paths.

## Windows deploy

`dev_deploy_to_kodi.bat` is the main local deployment tool for the Windows TV PC.

Expected loop:

```bat
git pull
dev_deploy_to_kodi.bat
```

It should copy the root skin to:

```text
C:\Users\Mateo\AppData\Roaming\Kodi\addons\skin.estuary.ziro
```

and companion add-ons to:

```text
C:\Users\Mateo\AppData\Roaming\Kodi\addons\plugin.program.ziro.games
C:\Users\Mateo\AppData\Roaming\Kodi\addons\script.ziro.games.launcher
C:\Users\Mateo\AppData\Roaming\Kodi\addons\service.ziro.games
```

## Generated files

Do not commit generated zips:

```text
dist/
*.zip
```

Do not commit patch state/manifests unless there is a specific reason.
