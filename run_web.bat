@echo off
rem ---------------------------------------------------------------------------
rem  Start the web app in a private environment.
rem
rem  Double-click this file. The first run creates a virtual environment in
rem  %LOCALAPPDATA% and installs the packages; later runs start instantly.
rem  The environment lives outside the project because this folder path is long
rem  enough that Windows hits its 260-character limit creating one in place.
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "VENV=%LOCALAPPDATA%\excel-automation-venv"

where python >nul 2>&1
if errorlevel 1 goto nopython

if not exist "%VENV%\Scripts\python.exe" (
    echo.
    echo First run: creating the web app environment. This takes a minute...
    python -m venv "%VENV%"
    if errorlevel 1 goto venvfail
    "%VENV%\Scripts\python.exe" -m pip install --quiet --upgrade pip
    "%VENV%\Scripts\python.exe" -m pip install --quiet -r requirements.txt
    if errorlevel 1 goto pipfail
)

echo.
echo Starting the web app.
echo Your browser will open at http://localhost:8501
echo Close this window to stop the server.
echo.

start "" http://localhost:8501
"%VENV%\Scripts\streamlit.exe" run app.py --server.port 8501 --browser.gatherUsageStats false
pause
exit /b 0

:nopython
echo.
echo Python is not installed, or not on PATH.
echo Install it from https://www.python.org/downloads/ and tick
echo "Add python.exe to PATH" during setup, then try again.
echo.
pause
exit /b 1

:venvfail
echo.
echo Could not create the environment at:
echo   %VENV%
echo.
pause
exit /b 1

:pipfail
echo.
echo Could not install the packages. Check your internet connection, then run:
echo   python -m pip install -r requirements.txt
echo.
pause
exit /b 1
