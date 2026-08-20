@echo off
setlocal
cd /d "%~dp0"

REM Double-click this file to open pinned Godot 4.7.1 on the tiny 2D fixture.
REM First run downloads into %LOCALAPPDATA%\HHGodotAgent\ (not the git repo).

echo [hh] Verifying Godot 4.7.1-stable pin...
python tools\godot\doctor.py --install
if errorlevel 1 (
  echo [hh] doctor failed. See tools\godot\README.md
  pause
  exit /b 1
)

set "GODOT_GUI=%LOCALAPPDATA%\HHGodotAgent\tooling\godot-4.7.1-stable\bin\Godot_v4.7.1-stable_win64.exe"
if not exist "%GODOT_GUI%" (
  echo [hh] missing "%GODOT_GUI%"
  pause
  exit /b 1
)

echo [hh] Opening editor: godot\test-projects\minimal-2d
start "" "%GODOT_GUI%" --editor --path "%~dp0godot\test-projects\minimal-2d"
endlocal
