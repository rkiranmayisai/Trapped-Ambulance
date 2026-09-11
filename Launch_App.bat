@echo off
title Trapped Ambulance App
cd /d "%~dp0"

:: Start python server in background if not already running
netstat -ano | findstr :5000 >nul 2>&1
if %errorlevel% neq 0 (
    start /b "" python app.py >nul 2>&1
    timeout /t 2 /nobreak >nul
)

:: Launch in native Standalone App Window (no URL bar, no search bar, pure App UI)
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app="http://localhost:5000" --window-size=1280,850
) else if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app="http://localhost:5000" --window-size=1280,850
) else (
    start "" "http://localhost:5000"
)
exit
