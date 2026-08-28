@echo off
setlocal
title MS365 Auto Renew WebUI
cd /d "%~dp0"
echo ===================================================
echo   Starting MS365 Auto Renew WebUI (FastAPI Server)
echo ===================================================

set "PYTHON_LAUNCHER="
if defined E5_PYTHON if exist "%E5_PYTHON%" set "PYTHON_LAUNCHER=%E5_PYTHON%"
if not defined PYTHON_LAUNCHER if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_LAUNCHER=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_LAUNCHER where py >nul 2>nul && set "PYTHON_LAUNCHER=py"
if not defined PYTHON_LAUNCHER (
    where python >nul 2>nul && set "PYTHON_LAUNCHER=python"
)
if not defined PYTHON_LAUNCHER goto :python_missing

"%PYTHON_LAUNCHER%" -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 goto :dependencies_missing
if /I "%~1"=="--check" (
    echo [OK] Project path, Python, run.py, FastAPI, and Uvicorn are available.
    exit /b 0
)

"%PYTHON_LAUNCHER%" run.py
goto :finished

:python_missing
echo [ERROR] Python was not found. Install Python 3.11 or 3.12 and try again.
echo         Then run: python -m pip install -r requirements-dev.txt
goto :failed

:dependencies_missing
echo [ERROR] Required Python packages are missing.
echo         Run: python -m pip install -r requirements-dev.txt
goto :failed

:finished
if errorlevel 1 goto :failed
exit /b 0

:failed
pause
exit /b 1
