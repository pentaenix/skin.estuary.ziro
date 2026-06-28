# service.ziro.games

This service is for behavior that should run in the background while Kodi is open.

Planned responsibilities:

- monitor active emulator processes
- record session duration
- return focus to Kodi after emulator exit
- integrate optional Windows helper for Home button behavior
- provide diagnostics/logging hooks

Do not block Kodi startup. Keep service loops lightweight and interruptible.
