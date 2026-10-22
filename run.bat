@echo off
rem ---------------------------------------------------------------------------
rem  Excel Cleanup Tool - double-click friendly launcher.
rem
rem  Drag an .xlsx / .csv file onto this file, or run:
rem      run.bat "C:\path\to\contacts.xlsx"
rem  Optionally name the columns:
rem      run.bat "C:\path\to\contacts.xlsx" "Email Address" "Mobile No"
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

if "%~1"=="" goto usage

where python >nul 2>&1
if errorlevel 1 goto nopython

python -c "import pandas, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo First run: installing required packages, this takes a minute...
    python -m pip install --quiet -r requirements.txt
    if errorlevel 1 goto pipfail
)

set "INPUT=%~1"
if not exist "%INPUT%" (
    echo.
    echo ERROR: cannot find the file:
    echo   %INPUT%
    echo.
    pause
    exit /b 1
)

set "OUTDIR=%~dp1output"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"
set "OUT=%OUTDIR%\%~n1_cleaned.xlsx"

set ARGS=--input "%INPUT%" --out "%OUT%"
if not "%~2"=="" set ARGS=%ARGS% --email-col "%~2"
if not "%~3"=="" set ARGS=%ARGS% --phone-col "%~3"

echo.
echo Cleaning: %INPUT%
python -m src.main %ARGS%
if errorlevel 1 goto failed

echo.
echo Saved: %OUT%
if not "%CLEANER_NO_OPEN%"=="1" start "" "%OUT%"
pause
exit /b 0

:usage
echo.
echo   Excel Cleanup Tool
echo   ------------------
echo   Drag an Excel or CSV file onto this file, or run:
echo       run.bat "C:\path\to\contacts.xlsx"
echo.
echo   To name your columns explicitly:
echo       run.bat "C:\path\to\contacts.xlsx" "Email Address" "Mobile No"
echo.
pause
exit /b 1

:nopython
echo.
echo Python is not installed, or not on PATH.
echo Install it from https://www.python.org/downloads/ and tick
echo "Add python.exe to PATH" during setup, then try again.
echo.
pause
exit /b 1

:pipfail
echo.
echo Could not install the required packages.
echo Check your internet connection, then run this once by hand:
echo     python -m pip install -r requirements.txt
echo.
pause
exit /b 1

:failed
echo.
echo Something went wrong - see the message above.
echo Your original file was not changed.
echo.
pause
exit /b 1
