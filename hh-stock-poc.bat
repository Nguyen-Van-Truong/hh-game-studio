@echo off
setlocal
cd /d "%~dp0"

REM Optional R1-WP4 fixture GUI (stock plugin only, no MCP).
REM Default human launcher remains hh-godot-editor.bat -> minimal-2d.

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

echo [hh] Opening editor: godot\test-projects\stock-poc
echo [hh] Disposable R1-WP4 plugin only. Not MCP. Not hh_agent.
start "" "%GODOT_GUI%" --editor --path "%~dp0godot\test-projects\stock-poc"
endlocal
