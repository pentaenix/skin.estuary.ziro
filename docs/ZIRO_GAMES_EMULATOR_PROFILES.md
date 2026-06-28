# Emulator Profiles

Initial profiles are created from the add-on settings during scan.

## Dolphin GameCube / Wii

```text
Executable: C:\Emulation\Emulators\Dolphin\Dolphin.exe
Arguments: -b -e "{rom_path}"
Process: Dolphin.exe
```

Supported first-pass extensions:

- `.rvz`
- `.iso`
- `.gcm`
- `.wbfs`
- `.wad`

## mGBA

```text
Executable: C:\Emulation\Emulators\mGBA\mGBA.exe
Arguments: -f "{rom_path}"
Process: mGBA.exe
```

Supported first-pass extensions:

- `.gba`
- `.gb`
- `.gbc`
- `.zip`

## Future profile fields

The database already has room for:

- working directory
- process name
- exit hotkey
- fullscreen flag
- return focus to Kodi flag

The next pass should expose these in a better Kodi settings UI or a dedicated setup route.
