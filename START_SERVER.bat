@echo off
chcp 65001 >nul
title Urganch Davlat Akademik Litseyi - Raqamli Kutubxona va ZiyoNET Portali
cd /d "%~dp0"
echo ================================================================
echo   ABU RAYHON BERUNIY NOMIDAGI URGANCH DAVLAT AKADEMIK LITSEYI
echo   ONLAYN KUTUBXONA VA ZIYONET / ZIYOUZ ELEKTRON MUTOLAA TIZIMI
echo ================================================================
echo.
echo Server http://127.0.0.1:8010 manzilida ishga tushirilmoqda...
start "" "http://127.0.0.1:8010"
python manage.py runserver 127.0.0.1:8010
pause
