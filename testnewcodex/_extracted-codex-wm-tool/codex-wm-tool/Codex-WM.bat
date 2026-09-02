@echo off
setlocal
cd /d "%~dp0"
title Codex WM 配置工具
cls
echo ========================================
echo    Codex WM 模型一键配置工具
echo ========================================
echo.
echo    1. 启用 WM 模型（先检测账号权限）
echo    2. 回滚到之前的配置
echo    0. 退出
echo.
echo ========================================
set /p choice=请选择 [1/2/0]:

if "%choice%"=="1" (
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Enable-CodexWM.ps1"
)
if "%choice%"=="2" (
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Enable-CodexWM.ps1" -Rollback
)

echo.
echo 按任意键退出...
pause >nul
