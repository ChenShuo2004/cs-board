@echo off
setlocal
cd /d "%~dp0"

if not exist "start-webapp.ps1" (
    echo Startup file start-webapp.ps1 was not found.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Python environment was not found. Please finish installation first.
    pause
    exit /b 1
)

where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo Node.js and npm were not found. Please install Node.js first.
    pause
    exit /b 1
)

if not exist "web\node_modules" (
    echo Frontend dependencies were not found. Run npm install in the web folder first.
    pause
    exit /b 1
)

echo Starting the whiteboard video workshop...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-webapp.ps1"
if errorlevel 1 (
    echo.
    echo Startup failed. See .webapp\launcher-error.log for details.
    pause
    exit /b 1
)

exit /b 0
