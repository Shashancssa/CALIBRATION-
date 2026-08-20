@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set PYTHON_CMD=py
) else (
    set PYTHON_CMD=python
)

echo Creating virtual environment in .venv ...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto :error

echo Installing required Python packages ...
call .venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :error
call .venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Setup complete.
echo Run the app with: .venv\Scripts\python.exe app.py
echo Or double-click run_windows.bat
exit /b 0

:error
echo.
echo Setup failed. Please confirm Python is installed and available in PATH.
exit /b 1
