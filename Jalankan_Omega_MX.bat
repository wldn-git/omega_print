@echo off
title Omega MX System - Launcher
cd /d "%~dp0"

echo Menjalankan Omega MX System...
call venv\Scripts\python.exe main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Terjadi kesalahan saat menjalankan aplikasi (Error code: %ERRORLEVEL%).
    pause
)
