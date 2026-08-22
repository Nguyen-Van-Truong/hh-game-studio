@echo off
setlocal
cd /d "%~dp0"

REM Human G2 VISIBLE Start: pinned Godot 4.7.1 on plugin-project (hh_agent).
REM Default human fixture stays hh-godot-editor.bat -> minimal-2d.
REM This launcher does not sign G2. Reviewer watches; harness never ticks G2.

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

echo [hh] CHECKLIST for the human reviewer:
echo [hh]   1. Look at res://r4w6/visible.tscn (this scene only).
echo [hh]   2. Confirm ONE VisibleSprite selected, Inspector shows Sprite2D,
echo [hh]      cyan overlay on the sprite, and timeline rows in HH Agent dock.
echo [hh]   3. Press Pause / Replay / Revert yourself on the dock.
echo [hh]   4. This run does not sign G2. Play is Alternative (not success).
echo [hh] Revert should use the drive checkpoint of visible.tscn, not snake.
echo [hh] Opening editor: godot\plugin-project
echo [hh] Then starting sidecar + visible drive (no second Godot).
echo [hh] Watch HH Agent Activity: bridge should become connected, timeline fills.
echo [hh] G2 VISIBLE is a HUMAN gate. Do not treat Start as a signed review.
start "" "%GODOT_GUI%" --editor --path "%~dp0godot\plugin-project"
python tools\godot\drive_visible.py
endlocal
