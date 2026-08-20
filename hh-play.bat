@echo off
setlocal EnableDelayedExpansion
REM ────────────────────────────────────────────────────────────────────
REM Choi game (khong mo editor). Pack ra %%TEMP%%\hh-gs-play\<ten>\
REM
REM   Double-click  → menu (1 snake / 2 platformer / 3 arena-brawl)
REM   hh-play.bat 1   hoac  hh-play.bat snake
REM   hh-play.bat 2   hoac  hh-play.bat platformer
REM   hh-play.bat 3   hoac  hh-play.bat scrap-yard
REM   hh-play.bat 4   hoac  hh-play.bat arena-brawl
REM   hh-play.bat C:\thu-muc-pack   (co gs-player.exe + manifest.json)
REM ────────────────────────────────────────────────────────────────────

if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
)

cd /d "%~dp0"

if not "%~1"=="" (
    if exist "%~f1\manifest.json" if exist "%~f1\gs-player.exe" (
        echo [gs] Packed folder: %~f1
        call :run_packed "%~f1"
        exit /b !ERRORLEVEL!
    )
)

set "GS_NAME="
if not "%~1"=="" (
    if "%~1"=="1" (
        set "GS_NAME=snake"
    ) else if /i "%~1"=="snake" (
        set "GS_NAME=snake"
    ) else if "%~1"=="2" (
        set "GS_NAME=platformer"
    ) else if /i "%~1"=="platformer" (
        set "GS_NAME=platformer"
    ) else if "%~1"=="3" (
        set "GS_NAME=scrap-yard"
    ) else if /i "%~1"=="scrap-yard" (
        set "GS_NAME=scrap-yard"
    ) else if "%~1"=="4" (
        set "GS_NAME=arena-brawl"
    ) else if /i "%~1"=="arena-brawl" (
        set "GS_NAME=arena-brawl"
    )
    if not "!GS_NAME!"=="" if exist "%~dp0games\!GS_NAME!\project.json" (
        set "GS_PROJECT=%~dp0games\!GS_NAME!"
    ) else if exist "%~dp0games\%~1\project.json" (
        set "GS_PROJECT=%~dp0games\%~1"
        set "GS_NAME=%~1"
    ) else if exist "%~f1\project.json" (
        set "GS_PROJECT=%~f1"
        for %%I in ("%~f1") do set "GS_NAME=%%~nxI"
    ) else (
        echo [gs] Khong thay game "%~1"
        echo [gs] Dung: 1/snake  2/platformer  3/scrap-yard  4/arena-brawl
        pause
        exit /b 1
    )
) else (
    echo.
    echo  HH Game Studio — choi game
    echo  1  snake         ^| A/D hoac mui ten: trai/phai. W/S: len/xuong. An cham cam.
    echo  2  platformer    ^| A/D: di. Space / W / Up: nhay. Lay 3 dong xu.
    echo  3  scrap-yard    ^| 2P: P1 mui ten+N/M/,/.  P2 WASD+1/2/3/4. Solo: WASD vs AI.
    echo  4  arena-brawl   ^| P1 mui ten+N/J. P2 WASD+1.
    echo.
    set /p "GS_CHOICE=Chon 1/2/3/4 (Enter = snake): "
    set "GS_CHOICE=!GS_CHOICE: =!"
    if "!GS_CHOICE!"=="2" (
        set "GS_NAME=platformer"
    ) else if /i "!GS_CHOICE!"=="platformer" (
        set "GS_NAME=platformer"
    ) else if "!GS_CHOICE!"=="3" (
        set "GS_NAME=scrap-yard"
    ) else if /i "!GS_CHOICE!"=="scrap-yard" (
        set "GS_NAME=scrap-yard"
    ) else if "!GS_CHOICE!"=="4" (
        set "GS_NAME=arena-brawl"
    ) else if /i "!GS_CHOICE!"=="arena-brawl" (
        set "GS_NAME=arena-brawl"
    ) else (
        set "GS_NAME=snake"
    )
    if exist "%~dp0games\!GS_NAME!\project.json" (
        set "GS_PROJECT=%~dp0games\!GS_NAME!"
    ) else (
        echo [gs] Thieu games\!GS_NAME!\project.json
        pause
        exit /b 1
    )
)

echo [gs] Game: %GS_NAME%
echo [gs]      %GS_PROJECT%

set "GS_PACKER="
if exist "%~dp0target\release\gs-player.exe" set "GS_PACKER=%~dp0target\release\gs-player.exe"
if "%GS_PACKER%"=="" if exist "%~dp0gs-player.exe" set "GS_PACKER=%~dp0gs-player.exe"

if "%GS_PACKER%"=="" (
    where cargo >nul 2>&1
    if errorlevel 1 (
        echo [gs] Chua co gs-player.exe va khong thay cargo trong PATH.
        echo [gs] Chay hh-game-studio.bat mot lan de build, roi chay lai file nay.
        echo [gs] Hoac mo game trong editor: hh-game-studio.bat games\%GS_NAME%  roi bam Play.
        pause
        exit /b 1
    )
    echo [gs] Building gs-player (release, lan dau co the mat vai phut)...
    cargo build -p gs-player --release
    if errorlevel 1 (
        echo [gs] BUILD FAILED
        pause
        exit /b 1
    )
    set "GS_PACKER=%~dp0target\release\gs-player.exe"
) else (
    echo [gs] Dung player da build: %GS_PACKER%
)

taskkill /IM gs-player.exe /F >nul 2>&1
set "GS_OUT=%TEMP%\hh-gs-play\%GS_NAME%"
if exist "%GS_OUT%" (
    rmdir /s /q "%GS_OUT%" 2>nul
)
mkdir "%GS_OUT%" 2>nul

echo [gs] Packing vao %GS_OUT%
"%GS_PACKER%" --project "%GS_PROJECT%" --out "%GS_OUT%"
if errorlevel 1 (
    echo [gs] PACK FAILED
    pause
    exit /b 1
)

echo [gs] Mo cua so Player. Dong cua so game de quay lai day.
echo [gs] (khong dung start — loi REJECT se hien trong cua so nay)
call :run_packed "%GS_OUT%"
set "GS_ERR=!ERRORLEVEL!"
if not "!GS_ERR!"=="0" (
    echo [gs] PLAYER EXIT !GS_ERR!
    pause
)
exit /b !GS_ERR!

:run_packed
pushd "%~1"
if not exist "gs-player.exe" (
    echo [gs] Thieu gs-player.exe trong %~1
    popd
    exit /b 1
)
if not exist "manifest.json" (
    echo [gs] Thieu manifest.json trong %~1
    popd
    exit /b 1
)
gs-player.exe --snapshot "%~1\manifest.json"
set "GS_RUN=!ERRORLEVEL!"
popd
exit /b !GS_RUN!
