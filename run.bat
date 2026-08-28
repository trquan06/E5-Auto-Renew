@echo off
title MS365 Auto Renew WebUI
cd /d "%~dp0ms365-auto-renew"
echo ===================================================
echo   Starting MS365 Auto Renew WebUI (FastAPI Server)
echo ===================================================
python run.py
pause
