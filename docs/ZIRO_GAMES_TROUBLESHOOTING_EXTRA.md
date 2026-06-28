# Troubleshooting Notes

## Skin does not appear

Check:

```text
C:\Users\Mateo\AppData\Roaming\Kodi\addons\skin.estuary.ziro\addon.xml
```

The add-on id must be `skin.estuary.ziro` and the `xbmc.gui` dependency must match the installed Kodi version.

Installed Kodi GUI dependency can be checked at:

```text
C:\Program Files\Kodi\addons\xbmc.gui\addon.xml
```

## Game scan finds 0 games

Check:

- source folder exists
- recursive scan setting
- file extensions match actual files
- files are not inside unsupported archives
- Kodi process can read the folder
- source is enabled

The scanner should show diagnostics instead of silently returning 0.

## GitHub Desktop does not show files

This repo may have a broad rule like:

```gitignore
*.py
```

If so, add exceptions:

```gitignore
!tools/
!tools/**
!ziro-addons/
!ziro-addons/**
```

## Do not commit generated zips

Generated files under `dist/` are local build artifacts.
