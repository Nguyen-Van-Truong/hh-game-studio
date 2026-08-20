@echo off
for %%I in ("%~dp0.") do call "%~dp0..\..\hh-play.bat" "%%~nxI"
