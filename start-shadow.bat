@echo off
rem Double-click to start Shadow on Windows. The first run sets everything up.
cd /d "%~dp0"
title Shadow

if not exist ".venv\Scripts\python.exe" (
    echo First run: setting Shadow up. This takes a minute...
    python -m venv .venv 2>nul || py -3 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo Python was not found. Install it from https://www.python.org/downloads/
        echo and tick "Add Python to PATH" during setup. Then run this again.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo Installing Shadow's packages failed. Check your internet connection and try again.
    pause
    exit /b 1
)
if not exist ".env" copy ".env.example" ".env" >nul

".venv\Scripts\python.exe" -m shadow.web
pause
