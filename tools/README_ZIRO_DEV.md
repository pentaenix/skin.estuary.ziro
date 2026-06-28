# Ziro Developer Tools

## Validate

```bash
python3 tools/ziro_validate_addons.py
```

On Windows:

```bat
py -3 tools\ziro_validate_addons.py
```

## Package

```bash
python3 tools/ziro_package_addons.py
```

On Windows:

```bat
py -3 tools\ziro_package_addons.py
```

Outputs go to `dist/` and should not be committed.

## Deploy to Windows Kodi

On Mateo's Windows TV PC:

```bat
dev_deploy_to_kodi.bat
```

This is the normal dev loop after `git pull`.
