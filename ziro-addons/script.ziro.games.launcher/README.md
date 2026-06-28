# script.ziro.games.launcher

This add-on is responsible for launching games.

Do not put launcher command-building in the skin. Keep it here or in shared library code.

Expected future behavior:

```text
input: game_id
load game + emulator profile from plugin database
validate executable and rom path
build command safely
start process non-blockingly
update last_played/play_count
log everything useful
return control to Kodi
```

Windows path handling is critical. Paths may contain spaces and non-ASCII characters.
