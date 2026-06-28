#!/usr/bin/env python3
from __future__ import annotations

import platform
from pathlib import Path

home = Path.home()
if platform.system().lower() == "darwin":
    print("macOS Kodi userdata:", home / "Library/Application Support/Kodi")
elif platform.system().lower() == "windows":
    print("Windows Kodi userdata: %APPDATA%\\Kodi")
else:
    print("Linux Kodi userdata:", home / ".kodi")
