# Launching Spec

Launching is a production feature, not a shell-command afterthought.

## Launch route

A game item should launch through:

```text
plugin://plugin.program.ziro.games/launch/<game_id>
```

or through a Kodi built-in/script call that passes `game_id` to `script.ziro.games.launcher`.

## Launcher responsibilities

The launcher must:

- load game and emulator profile from SQLite
- verify ROM path exists
- verify emulator executable exists
- build arguments from template
- quote paths correctly
- set working directory
- start emulator non-blockingly
- write clear Kodi log lines
- update play_count and last_played
- return control to Kodi as cleanly as possible

## Path quoting

Windows paths with spaces must work. Avoid building commands as one fragile string when a list/array is possible. Prefer subprocess APIs that accept argument arrays.

## Token replacement

Support tokens:

```text
{rom_path}
{rom_dir}
{rom_file}
{rom_name}
{core_path}
```

## Dolphin profiles

```text
Dolphin Wii/GameCube
executable: C:\Emulation\Emulators\Dolphin\Dolphin.exe
arguments: -b -e "{rom_path}"
process_name: Dolphin.exe
```

## mGBA profile

```text
mGBA
executable: C:\Emulation\Emulators\mGBA\mGBA.exe
arguments: -f "{rom_path}"
process_name: mGBA.exe
```

## Error UI

If launch fails, show a Kodi notification with a concise reason and log details:

```text
Dolphin executable not found
Game file not found
Launch profile missing
Failed to start process
```

## Return to Kodi

Phase 1: Kodi remains running behind emulator.

Phase 2: service watches process exit and focuses Kodi.

Phase 3: optional Windows helper maps air-mouse Home to close emulator/focus Kodi.
