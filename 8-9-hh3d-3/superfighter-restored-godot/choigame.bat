@echo off
cd /d "%~dp0"
set "GODOT=%~dp0..\studio\.local\tooling\godot-4.7.2-stable\Godot_v4.7.2-stable_win64.exe"
if not exist "%GODOT%" (
  echo Khong thay Godot pin: %GODOT%
  pause
  exit /b 2
)
echo P1: WASD, J dam, K ban.  P2: mui ten, Num1 dam, Num2 ban.
"%GODOT%" --path . --display-driver windows --rendering-method gl_compatibility
