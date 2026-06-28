# Ziro Games Install Notes

After applying the patch from the root of your Estuary fork:

```bash
python3 tools/ziro_validate_addons.py
python3 tools/ziro_package_addons.py
```

Generated zips are written to `dist/`.

Install in Kodi in this order:

1. `plugin.program.ziro.games-0.1.0.zip`
2. `script.ziro.games.launcher-0.1.0.zip`
3. `service.ziro.games-0.1.0.zip`
4. Your packaged skin zip, if your fork's root `addon.xml` has already been renamed to a non-default skin id.

If the skin package still has `id="skin.estuary"`, do not install it over the built-in skin. Rename your fork first.

## Testing the first flow

1. Install the three Ziro add-ons.
2. Open `Ziro Games` from Program add-ons.
3. With mock library enabled, you should see design placeholder games.
4. In the skin, select the existing Games menu item. If the XML token was found, it should open the Ziro Games plugin instead of Kodi's native Games window.

## Real scan

Open Ziro Games settings and configure:

- GameCube folder
- Wii folder
- Game Boy Advance folder
- Dolphin executable
- mGBA executable

Then run:

```text
Ziro Games -> Scan / Refresh Library
```

Mock games are for skin layout only. They cannot launch.
