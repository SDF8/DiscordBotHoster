@echo off
setlocal
chcp 65001 >nul
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo ============================================
echo   Discord Bot Hoster - EXE Builder
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    pause
    exit /b 1
)

echo [1/3] Installing build dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/3] Building executable with PyInstaller...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "DiscordBotHoster" ^
    --collect-all customtkinter ^
    main.py
if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo [3/3] Done.
echo Build output: "%SCRIPT_DIR%dist\DiscordBotHoster.exe"
pause