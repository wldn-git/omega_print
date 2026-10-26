@echo off
title Omega MX System - Launcher
cd /d "%~dp0"

echo ========================================================================
echo OMEGA MX - BATCH PRINTING & QC SYSTEM (v5.0)
echo Memeriksa lingkungan sistem...
echo ========================================================================

:: 1. Cek apakah folder venv sudah ada
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Virtual Environment (venv) belum ditemukan.
    echo [INFO] Memeriksa instalasi Python di sistem Windows...
    
    where python >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [ERROR] Python tidak terdeteksi di sistem PATH!
        echo Silakan instal Python 3.10 ke atas (Pastikan mencentang "Add Python to PATH").
        echo Unduh installer Python resmi: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    
    echo [INFO] Membuat Virtual Environment baru (venv)...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Gagal membuat virtual environment.
        pause
        exit /b 1
    )
    
    echo [INFO] Menginstal dependensi dari requirements.txt...
    call venv\Scripts\python.exe -m pip install --upgrade pip
    call venv\Scripts\pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [WARNING] Instalasi dependensi mengalami kendala.
        echo Pastikan komputer terhubung ke internet untuk instalasi awal.
        pause
        exit /b 1
    )
    echo [SUCCESS] Lingkungan venv & dependensi berhasil disiapkan!
    echo.
)

:: 2. Jalankan aplikasi utama
echo Menjalankan Omega MX System...
call venv\Scripts\python.exe main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Terjadi kesalahan saat menjalankan aplikasi (Error code: %ERRORLEVEL%).
    pause
)
