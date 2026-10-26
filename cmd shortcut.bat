@echo off
title Terminal Omega MX

:: Masuk ke folder project secara dinamis
cd /d "%~dp0"

:: Aktivasi Virtual Environment (venv)
call venv\Scripts\activate.bat

echo =======================================================
echo Lingkungan Virtual (venv) sudah aktif!
echo Aplikasi siap dijalankan.
echo =======================================================
echo.


:: Tahan layar jika aplikasi ditutup agar bisa lihat pesan error (jika ada)
cmd /k