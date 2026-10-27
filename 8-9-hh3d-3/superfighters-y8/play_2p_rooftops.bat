@echo off
setlocal
set "GODOT_BIN=%~dp0..\.local\tooling\godot-4.7.2-stable\Godot_v4.7.2-stable_win64.exe"
if not exist "%GODOT_BIN%" (
    set "GODOT_BIN=%~dp0..\old-gameproject\superagent copy\.local\tooling\godot-4.7.2-stable\Godot_v4.7.2-stable_win64.exe"
)
if not exist "%GODOT_BIN%" (
    set "GODOT_BIN=%LOCALAPPDATA%\HHGodotAgent\tooling\godot-4.7.1-stable\bin\Godot_v4.7.1-stable_win64.exe"
)
echo Starting Superfighters Y8 - 2P Local VS on Rooftops...
"%GODOT_BIN%" --path "%~dp0." -- --quick-match --map=rooftops --mode=vs_2p
endlocal
