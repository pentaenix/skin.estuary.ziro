# Ziro Companion Add-ons

These add-ons work with the `skin.estuary.ziro` fork.

## `plugin.program.ziro.games`

The main game library add-on. It should own database, scanner, metadata/artwork, routes, and Kodi ListItem generation.

## `script.ziro.games.launcher`

Launch bridge for games. It should own emulator command construction and process start.

## `service.ziro.games`

Background service for session watching, focus restoration, and future hotkey/Home behavior.

## Rule of thumb

- Skin displays.
- Plugin lists and scans.
- Script launches.
- Service watches.
