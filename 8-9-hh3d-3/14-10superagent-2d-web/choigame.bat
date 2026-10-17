@echo off
cd /d "%~dp0"
where npm >nul 2>&1
if errorlevel 1 (
  echo Khong tim thay npm. Cai Node.js roi chay lai file nay.
  pause
  exit /b 1
)
if not exist node_modules (
  echo Dang cai dependencies...
  call npm install
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
echo Dang mo Superagent 2D Web. Dong cua so nay de tat game.
call npm run dev -- --open --host 127.0.0.1 --port 5173
