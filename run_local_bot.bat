@echo off
title Discord Music Bot (Local Host)
cd /d "%~dp0"
echo ========================================================
echo         Discord Music Bot - Local Host Running
echo ========================================================
echo.
python src/bot.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Bot exited with error code %ERRORLEVEL%.
    pause
)
