@echo off
REM ────────────────────────────────────────────────────────────────────
REM HH Game Studio launcher
REM
REM Muc tieu:
REM   * Luc nao cung chay ban gs-editor + gs-player moi nhat khop source.
REM   * Mo cua so that (khong an nhu tools\gs.ps1 open).
REM   * KHONG mo chinh repo lam project (tranh WAL/lock vao source).
REM
REM Cach dung:
REM   * Double-click file nay, hoac keo mot folder project tha vao.
REM   * Mac dinh mo games\snake (roi platformer, roi playground).
REM   * cargo build --release incremental: lan dau sau clean ~vai phut;
REM     lan sau khi khong sua: < 1 giay.
REM ────────────────────────────────────────────────────────────────────

if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
)

cd /d "%~dp0"
if exist "%USERPROFILE%\.cargo\bin\cargo.exe" (
    set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
)

if not "%~1"=="" (
    set "GS_PROJECT=%~f1"
) else if exist "%~dp0games\snake\project.json" (
    set "GS_PROJECT=%~dp0games\snake"
) else if exist "%~dp0games\platformer\project.json" (
    set "GS_PROJECT=%~dp0games\platformer"
) else (
    set "GS_PROJECT=%~dp0playground"
)

if not exist "%GS_PROJECT%" (
    mkdir "%GS_PROJECT%"
)

echo [gs] Building latest gs-editor + gs-player + gs-cli (release, incremental)...
cargo build -p gs-editor -p gs-player -p gs-cli --release
if errorlevel 1 (
    echo [gs] BUILD FAILED — keep the previous .exe and bail out.
    pause
    exit /b 1
)

echo [gs] Refreshing binaries next to this bat...
copy /y target\release\gs-editor.exe . >nul
copy /y target\release\gs-player.exe . >nul
copy /y target\release\gs-cli.exe . >nul

set "GS_PLAYER_EXE=%~dp0gs-player.exe"
set "GS_EDITOR=%~dp0gs-editor.exe"
set "GS_CLI=%~dp0gs-cli.exe"
set "GS_ROOT=%GS_PROJECT%"

echo [gs] Project: %GS_PROJECT%
echo [gs] CLI (terminal khac):  .\tools\gs.ps1 send entity.spawn "{\"name\":\"hero\"}"
echo [gs] Launching window...
start "" "%~dp0gs-editor.exe" "%GS_PROJECT%"
