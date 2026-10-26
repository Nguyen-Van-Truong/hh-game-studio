@echo off
setlocal

rem Launch the playable two-player Relay Yard slice with the pinned Godot build.
rem run_guarded.py assigns the process lease and writes a fresh run manifest.
set "PRODUCT_ROOT=%~dp0.."
pushd "%PRODUCT_ROOT%"
if errorlevel 1 (
  echo Could not enter the product directory.
  pause
  exit /b 1
)

for /f %%T in ('powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')"') do set "RUN_STAMP=%%T"
if not defined RUN_STAMP set "RUN_STAMP=%RANDOM%"
set "COMMAND_ID=cmd.manual.play.two-player.%RUN_STAMP%"
set "IMPORT_COMMAND_ID=cmd.manual.import.two-player.%RUN_STAMP%"
set "GODOT=.local\tooling\godot-4.7.2-stable\Godot_v4.7.2-stable_win64.exe"

if not exist "%GODOT%" (
  echo Pinned Godot executable was not found:
  echo   %CD%\%GODOT%
  popd
  pause
  exit /b 2
)

python --version >nul 2>&1
if errorlevel 1 (
  echo Python is required to start the game. Install Python 3 and enable Add to PATH.
  popd
  pause
  exit /b 3
)

rem Always refresh the import cache: one sidecar cannot prove that all source
rem textures and their .godot cache targets still exist or are current.
echo Checking Godot assets before opening the match.
  python tools\run_guarded.py --project-root . --timeout 180 --command-id "%IMPORT_COMMAND_ID%" --source . --mode manual-import -- "%GODOT%" --headless --import --path .
  if errorlevel 1 (
    echo Godot asset import failed. Details are in .local\runs.
    popd
    pause
    exit /b 4
  )

echo Starting Relay Yard - two players on one keyboard.
echo P1: WASD and J K L ; Q cycles slots    P2: arrows and Numpad 1 2 3 4 5, Num Lock on.
echo Pick up weapons: hold Down + Punch.  Esc: pause.  Close the game window to exit.
echo Keep this console open while playing. Session limit: four hours.
python tools\run_guarded.py --project-root . --timeout 14400 --visible --command-id "%COMMAND_ID%" --source . --seed 1 --map classic_rooftops --mode two_player -- "%GODOT%" --path . --display-driver windows --rendering-method gl_compatibility --scene res://game/ui/match_room.tscn --classic-rooftops %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo The game stopped with code %EXIT_CODE%. Details are in .local\runs.
  pause
)
popd
exit /b %EXIT_CODE%
