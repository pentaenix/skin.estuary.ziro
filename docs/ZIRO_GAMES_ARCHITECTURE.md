# Ziro Games Architecture

This repo remains an Estuary skin fork, but the game-center work is split into a production add-on suite:

- `skin.estuary.zirogames` — the Estuary-style skin fork. This patch only reroutes the existing Games menu item when it can find the expected Estuary XML token.
- `plugin.program.ziro.games` — the Kodi-native game library. It owns the SQLite database and exposes routes the skin can use as widgets/shelves.
- `script.ziro.games.launcher` — launches a selected game through the configured emulator profile.
- `service.ziro.games` — watches the active emulator session and tries to return focus to Kodi when the emulator exits.

The goal is not to show Playnite inside Kodi. The goal is to make Kodi itself browse games like media, with Playnite/AEL/AKL optional references only.

## Current routes

- `plugin://plugin.program.ziro.games/home`
- `plugin://plugin.program.ziro.games/continue`
- `plugin://plugin.program.ziro.games/recent`
- `plugin://plugin.program.ziro.games/favorites`
- `plugin://plugin.program.ziro.games/platforms`
- `plugin://plugin.program.ziro.games/platform/<platform_id>`
- `plugin://plugin.program.ziro.games/genres`
- `plugin://plugin.program.ziro.games/genre/<genre_id>`
- `plugin://plugin.program.ziro.games/launch?game_id=<id>`

## First-pass skin patch

The patch changes Estuary's existing Games side-menu action:

```text
ActivateWindow(Games)
```

to:

```text
ActivateWindow(Programs,plugin://plugin.program.ziro.games/home,return)
```

It also removes the dependency on Kodi's RetroPlayer setting for showing the Games item. This is intentionally surgical so the skin can still be iterated safely.

## Next skin work

The next production pass should replace/extend the Games widget group with Estuary-style shelves that point directly to:

```text
plugin://plugin.program.ziro.games/continue
plugin://plugin.program.ziro.games/recent
plugin://plugin.program.ziro.games/favorites
plugin://plugin.program.ziro.games/platform/gamecube
plugin://plugin.program.ziro.games/platform/wii
plugin://plugin.program.ziro.games/platform/gba
plugin://plugin.program.ziro.games/genres
```

That is where the home screen starts looking like Movies: rows by console, rows by genre, Continue Playing, Recently Added, and Favorites.
