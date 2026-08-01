@echo off
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

rem ---- find a real Python (the Microsoft Store stub fails --version) ----
set "PYCMD="
py -3 --version >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD python --version >nul 2>nul && set "PYCMD=python"
if not defined PYCMD python3 --version >nul 2>nul && set "PYCMD=python3"

if not defined PYCMD (
    echo ============================================================
    echo  Python was not found on this computer.
    echo.
    echo  1. Install it from  https://www.python.org/downloads/
    echo  2. During setup, tick "Add python.exe to PATH".
    echo  3. Run play.bat again.
    echo.
    echo  NOTE: typing "python" opening the Microsoft Store means
    echo  Windows has a placeholder, not real Python - use the
    echo  python.org installer.
    echo ============================================================
    pause
    exit /b 1
)

echo Using: & %PYCMD% --version
echo.
%PYCMD% -m fs_bot.cli.app --save autosave.json
if errorlevel 1 (
    echo.
    echo ============================================================
    echo  The game stopped with an error - the message above this
    echo  box explains why. Common fixes:
    echo   - "No module named fs_bot": extract the ENTIRE zip and
    echo     run play.bat from inside the fs-bot folder.
    echo   - Python version too old: install 3.10 or newer.
    echo  Please copy the error text if you need help.
    echo ============================================================
)
echo.
echo (game over or exited - this window stays open until you press a key)
pause
