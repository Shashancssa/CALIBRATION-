@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup first...
    call setup_windows.bat
    if errorlevel 1 exit /b 1
)

echo Starting Calibration app at http://127.0.0.1:5000 ...
.venv\Scripts\python.exe app.py
