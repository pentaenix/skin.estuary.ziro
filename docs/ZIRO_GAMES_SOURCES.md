# Ziro Games Sources

Games should not require moving ROMs into hardcoded folders.

The plugin now exposes a source manager inside Kodi:

```text
Games -> Sources
```

From there you can add:

- Nintendo GameCube source folders
- Nintendo Wii source folders
- Game Boy Advance source folders

Each source uses Kodi's folder browser, closer to how Movies/TV sources are chosen. Multiple sources per platform are supported.

After adding a source, choose **Scan now** or run:

```text
Games -> Scan / Refresh Library
```

## Current local-path limitation

The first production path targets the user's Windows TV PC with local/direct-attached storage. Dolphin and mGBA need paths they can open from Windows. Kodi network paths such as `smb://...` may scan, but most standalone emulators will not launch them unless they are mapped to normal Windows drive paths.
