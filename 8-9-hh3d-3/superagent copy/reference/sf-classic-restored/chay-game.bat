@echo off
cd /d "%~dp0"
echo Mo http://127.0.0.1:8766/play-local.html (Ruffle + 00-original.swf)
start "" "http://127.0.0.1:8766/play-local.html"
echo Nhan Ctrl+C de tat server.
python -m http.server 8766
