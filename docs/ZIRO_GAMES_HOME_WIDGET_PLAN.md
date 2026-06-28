# Games Home Widget Plan

The next major product step is making Games appear on the Kodi home page like Movies.

## Current problem

The current scaffold can open the Ziro Games plugin, but the desired UX is not a nested plugin menu. The target is Estuary-style rows directly on the home surface.

## Target UX

```text
Kodi Home
  Games selected
    Continue Playing row
    Recently Added row
    Favorites row
    Nintendo Wii row
    Game Boy Advance row
    GameCube row
    RPG row
    Platformer row
```

Clicking a game tile launches the game. It should not open an intermediate details screen by default.

## Implementation approach

1. Inspect existing Estuary home widgets for Movies/TV/Music.
2. Identify reusable includes/controls.
3. Add Games widgets that point to plugin routes.
4. Make plugin routes return game ListItems with art and launch URLs.
5. Keep all skin styling copied from existing Estuary widget patterns.

## Important limitation to investigate

Kodi skin XML may not support truly arbitrary dynamic rows generated solely by a plugin. If dynamic platform/genre rows cannot be enumerated at runtime from skin XML, use one of these production-safe approaches:

### Option A: Fixed row slots

Expose a finite set of plugin routes:

```text
/home_widget/1
/home_widget/2
/home_widget/3
...
```

Each route returns items for the nth configured row. The skin labels can also come from plugin-provided properties where supported, or from a companion generated include.

### Option B: Generated skin include

At deploy/build time, generate a small XML include file based on configured platforms/genres. This is more complex because user configuration lives in Kodi userdata, not the repo.

### Option C: Plugin home view as temporary fallback

Use the plugin route as a rich game hub while documenting that true home row integration is the next skin patch.

Do not pretend a limitation does not exist. Discover it and document the chosen path.

## Row content routes

Needed routes:

```text
plugin://plugin.program.ziro.games/continue
plugin://plugin.program.ziro.games/recent
plugin://plugin.program.ziro.games/favorites
plugin://plugin.program.ziro.games/platform/<platform_id>
plugin://plugin.program.ziro.games/genre/<genre_id>
```

Each route should return launchable game ListItems.

## Empty library fallback

When there are no games, Games should not be blank. Show:

```text
Add Game Source
Scan / Refresh Library
Settings
Troubleshooting / Diagnostics
```

## Done when

- Games has direct rows on home.
- Rows use Estuary visuals.
- One click launches.
- Empty state is helpful.
- Color/theme settings remain intact.
