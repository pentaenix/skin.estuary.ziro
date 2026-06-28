@echo off
setlocal EnableExtensions

REM ============================================================
REM Ziro Kodi Games - Dev Deploy Script
REM Run this from the root of the skin.estuary.ziro repo.
REM Target user: Mateo
REM ============================================================

set "REPO=%~dp0"
set "REPO=%REPO:~0,-1%"

set "SKIN_ID=skin.estuary.ziro"
set "PLUGIN_ID=plugin.program.ziro.games"
set "LAUNCHER_ID=script.ziro.games.launcher"
set "SERVICE_ID=service.ziro.games"

set "KODI_DATA=C:\Users\Mateo\AppData\Roaming\Kodi"
set "KODI_EXE=C:\Program Files\Kodi\Kodi.exe"

echo.
echo === Ziro Kodi Games Dev Deploy ===
echo Repo: %REPO%
echo.

REM ------------------------------------------------------------
REM Basic repo checks
REM ------------------------------------------------------------

if not exist "%REPO%\addon.xml" (
  echo ERROR: addon.xml not found.
  echo Run this BAT from the root of the skin.estuary.ziro repo.
  echo.
  pause
  exit /b 1
)

findstr /C:"id=\"%SKIN_ID%\"" "%REPO%\addon.xml" >nul
if errorlevel 1 (
  echo ERROR: Root addon.xml does not use id="%SKIN_ID%".
  echo.
  echo Current root addon line:
  findstr /C:"<addon " "%REPO%\addon.xml"
  echo.
  echo Fix addon.xml before deploying, otherwise Kodi may conflict with default Estuary.
  echo.
  pause
  exit /b 1
)

if not exist "%REPO%\ziro-addons\%PLUGIN_ID%\addon.xml" (
  echo ERROR: Missing %PLUGIN_ID%.
  pause
  exit /b 1
)

if not exist "%REPO%\ziro-addons\%LAUNCHER_ID%\addon.xml" (
  echo ERROR: Missing %LAUNCHER_ID%.
  pause
  exit /b 1
)

if not exist "%REPO%\ziro-addons\%SERVICE_ID%\addon.xml" (
  echo ERROR: Missing %SERVICE_ID%.
  pause
  exit /b 1
)

REM ------------------------------------------------------------
REM Find Kodi userdata/addons folder
REM ------------------------------------------------------------

if not exist "%KODI_DATA%" (
  echo WARN: Expected Kodi userdata folder not found:
  echo %KODI_DATA%
  echo.
  echo Trying APPDATA fallback...
  set "KODI_DATA=%APPDATA%\Kodi"
)

if not exist "%KODI_DATA%" (
  echo WARN: APPDATA Kodi folder not found.
  echo Trying Microsoft Store Kodi path...
  set "KODI_DATA=%LOCALAPPDATA%\Packages\XBMCFoundation.Kodi_4n2hpmxwrvr6p\LocalCache\Roaming\Kodi"
)

if not exist "%KODI_DATA%" (
  echo ERROR: Could not find Kodi userdata folder.
  echo Open Kodi once on this Windows machine, then run this script again.
  echo.
  pause
  exit /b 1
)

set "KODI_ADDONS=%KODI_DATA%\addons"

if not exist "%KODI_ADDONS%" (
  mkdir "%KODI_ADDONS%"
)

echo Kodi data:   %KODI_DATA%
echo Kodi addons: %KODI_ADDONS%
echo.

REM ------------------------------------------------------------
REM Find Python
REM ------------------------------------------------------------

set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py -3"
)

if "%PYTHON_CMD%"=="" (
  where python >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=python"
  )
)

if "%PYTHON_CMD%"=="" (
  echo ERROR: Could not find Python.
  echo Install Python 3 for Windows or enable the Python launcher.
  echo.
  pause
  exit /b 1
)

echo Python: %PYTHON_CMD%
echo.

REM ------------------------------------------------------------
REM Validate and package
REM ------------------------------------------------------------

echo === Validating add-ons ===
%PYTHON_CMD% "%REPO%\tools\ziro_validate_addons.py"
if errorlevel 1 (
  echo.
  echo ERROR: Validation failed.
  pause
  exit /b 1
)

echo.
echo === Packaging add-ons ===
%PYTHON_CMD% "%REPO%\tools\ziro_package_addons.py"
if errorlevel 1 (
  echo.
  echo ERROR: Packaging failed.
  pause
  exit /b 1
)

echo.
echo === Closing Kodi if running ===
tasklist /FI "IMAGENAME eq Kodi.exe" 2>NUL | find /I "Kodi.exe" >NUL
if not errorlevel 1 (
  taskkill /IM Kodi.exe /T /F >nul 2>nul
  timeout /t 2 /nobreak >nul
) else (
  echo Kodi is not running.
)

REM ------------------------------------------------------------
REM Deploy skin fork directly to Kodi/addons
REM ------------------------------------------------------------

echo.
echo === Deploying %SKIN_ID% ===

robocopy "%REPO%" "%KODI_ADDONS%\%SKIN_ID%" /MIR ^
  /XD ".git" ".github" "dist" "ziro-addons" "tools" "docs" "__pycache__" ^
  /XF "patch" "*.zip" "*.bak" ".DS_Store" ".ziro_games_patch_state.json" ".ziro_games_initial_setup_manifest.json" "ZIRO_GAMES_PATCH_README.md" "dev_deploy_to_kodi.bat" ^
  /NFL /NDL /NJH /NJS /NP

if errorlevel 8 (
  echo ERROR: Failed deploying %SKIN_ID%.
  pause
  exit /b 1
)


REM ------------------------------------------------------------
REM ZIRO_SYNC_ESTUARY_VISUAL_ASSETS
REM Keep the fork visually identical to stock Estuary during dev deploy.
REM This restores stock color/theme choices when the repo snapshot is missing them.
REM ------------------------------------------------------------

set "STOCK_ESTUARY=C:\Program Files\Kodi\addons\skin.estuary"
if not exist "%STOCK_ESTUARY%" (
  if exist "%KODI_EXE%" (
    for %%I in ("%KODI_EXE%") do set "KODI_INSTALL_DIR=%%~dpI"
    if exist "%KODI_INSTALL_DIR%addons\skin.estuary" set "STOCK_ESTUARY=%KODI_INSTALL_DIR%addons\skin.estuary"
  )
)

if exist "%STOCK_ESTUARY%\colors" (
  echo Syncing stock Estuary colors...
  robocopy "%STOCK_ESTUARY%\colors" "%KODI_ADDONS%\%SKIN_ID%\colors" /MIR /NFL /NDL /NJH /NJS /NP >nul
)

if exist "%STOCK_ESTUARY%\themes" (
  echo Syncing stock Estuary themes...
  robocopy "%STOCK_ESTUARY%\themes" "%KODI_ADDONS%\%SKIN_ID%\themes" /MIR /NFL /NDL /NJH /NJS /NP >nul
)

if exist "%STOCK_ESTUARY%\media" if not exist "%KODI_ADDONS%\%SKIN_ID%\media" (
  echo Copying missing stock Estuary media assets...
  robocopy "%STOCK_ESTUARY%\media" "%KODI_ADDONS%\%SKIN_ID%\media" /MIR /NFL /NDL /NJH /NJS /NP >nul
)

REM ------------------------------------------------------------
REM Deploy companion add-ons
REM ------------------------------------------------------------

echo.
echo === Deploying %PLUGIN_ID% ===
robocopy "%REPO%\ziro-addons\%PLUGIN_ID%" "%KODI_ADDONS%\%PLUGIN_ID%" /MIR ^
  /XD "__pycache__" ^
  /XF ".DS_Store" ^
  /NFL /NDL /NJH /NJS /NP

if errorlevel 8 (
  echo ERROR: Failed deploying %PLUGIN_ID%.
  pause
  exit /b 1
)

echo.
echo === Deploying %LAUNCHER_ID% ===
robocopy "%REPO%\ziro-addons\%LAUNCHER_ID%" "%KODI_ADDONS%\%LAUNCHER_ID%" /MIR ^
  /XD "__pycache__" ^
  /XF ".DS_Store" ^
  /NFL /NDL /NJH /NJS /NP

if errorlevel 8 (
  echo ERROR: Failed deploying %LAUNCHER_ID%.
  pause
  exit /b 1
)

echo.
echo === Deploying %SERVICE_ID% ===
robocopy "%REPO%\ziro-addons\%SERVICE_ID%" "%KODI_ADDONS%\%SERVICE_ID%" /MIR ^
  /XD "__pycache__" ^
  /XF ".DS_Store" ^
  /NFL /NDL /NJH /NJS /NP

if errorlevel 8 (
  echo ERROR: Failed deploying %SERVICE_ID%.
  pause
  exit /b 1
)

REM ------------------------------------------------------------
REM Restart Kodi
REM ------------------------------------------------------------

echo.
echo === Restarting Kodi ===

if exist "%KODI_EXE%" (
  start "" "%KODI_EXE%"
) else (
  echo WARN: Kodi.exe not found at:
  echo %KODI_EXE%
  echo.
  echo Start Kodi manually.
)

echo.
echo === Deploy complete ===
echo.
echo Installed to:
echo %KODI_ADDONS%\%SKIN_ID%
echo %KODI_ADDONS%\%PLUGIN_ID%
echo %KODI_ADDONS%\%LAUNCHER_ID%
echo %KODI_ADDONS%\%SERVICE_ID%
echo.
echo Kodi log:
echo %KODI_DATA%\kodi.log
echo.
pause
exit /b 0