# Dynamic Game Library Spec

The game library must be user-defined. Do not hardcode console source buttons.

## Platform

A platform/console is a user-facing grouping, for example:

```text
Nintendo Wii
Game Boy Advance
Nintendo GameCube
Sega Dreamcast
Arcade
```

Required fields:

```text
id
name
short_name
manufacturer optional
sort_order
visible
```

## Source

A source is a folder containing games for a platform.

Required fields:

```text
id
platform_id
name
folder_path
recursive
extensions
emulator_profile_id
enabled
last_scan_at
last_scan_seen_count
last_scan_accepted_count
last_scan_inserted_count
last_scan_updated_count
last_scan_error
```

## Emulator profile

A profile maps a platform/source to a launch command.

Required fields:

```text
id
name
platform_id optional
executable_path
arguments_template
working_directory
process_name
exit_hotkey
fullscreen
return_focus_to_kodi
```

## Game

A game belongs to a platform and source.

Required fields:

```text
id
title
sort_title
platform_id
source_id
rom_path
rom_size
rom_mtime
emulator_profile_id
release_year
developer
publisher
description
cover_path
fanart_path
logo_path
screenshot_path
favorite
hidden
date_added
last_seen_at
last_played
play_count
total_play_time
manual_title
manual_metadata_locked
```

## Scan behavior

A scan should:

1. Load enabled sources.
2. Verify folder exists.
3. Walk recursively if configured.
4. Normalize extensions to lowercase without dot.
5. Skip unsupported extensions.
6. Clean file names into default titles.
7. Upsert games by stable key such as normalized absolute path or source_id + relative path.
8. Preserve manual edits.
9. Mark missing games hidden/stale rather than deleting immediately.
10. Store scan stats.

## Diagnostics

When a scan finds 0 games, the UI must expose why:

```text
folder missing
no files found
files found but no matching extensions
permissions/read error
database error
```

Show example skipped files with extension and reason.
