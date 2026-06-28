# Ziro Games Troubleshooting

## Kodi log paths

Windows classic install:

```text
%APPDATA%\Kodi\kodi.log
```

Windows Store install:

```text
%LOCALAPPDATA%\Packages\XBMCFoundation.Kodi_4n2hpmxwrvr6p\LocalCache\Roaming\Kodi\kodi.log
```

macOS:

```text
~/Library/Application Support/Kodi/kodi.log
```

## Games menu still opens native Kodi Games

The patch only changes `xml/Home.xml` if it finds the exact Estuary token `ActivateWindow(Games)`. If your fork has already changed the Home XML, patch it manually to:

```text
ActivateWindow(Programs,plugin://plugin.program.ziro.games/home,return)
```

## Mock games show but real games do not

- Check Ziro Games settings.
- Confirm your ROM folders exist on the Kodi machine.
- Run `Scan / Refresh Library`.
- Disable mock library when you want to verify real data only.

## Clicking a mock game errors

That is expected. Mock games exist to let you play with skin rows before scanning a real library.

## Emulator does not launch

Check:

- the emulator executable path exists
- the ROM path exists
- the game is not a mock item
- the launch command in `kodi.log`
