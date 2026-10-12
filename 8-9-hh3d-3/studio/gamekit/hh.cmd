@echo off
rem HH gamekit launcher: hh.cmd <command> ...  (see zdoc/12-10-huong-dan-dung-cong-cu-godot-blender.txt)
setlocal
set "HH_BASE=%~dp0..\.."
set "PYTHONPATH=%HH_BASE%;%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"
python -B -m studio.gamekit.hh %*
exit /b %ERRORLEVEL%
