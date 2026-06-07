@echo off
title Building Supermarket App EXE...
color 0A

echo.
echo ============================================================
echo   SUPERMARKET APP - EXE BUILDER
echo ============================================================
echo.

:: Activate the virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate venv. Make sure venv exists.
    pause
    exit /b 1
)

echo [1/3] Installing PyInstaller...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller.
    pause
    exit /b 1
)

echo [2/3] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo [3/3] Building EXE (this takes 3-8 minutes, please wait)...
echo.
pyinstaller supermarket.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ============================================================
    echo   BUILD FAILED. Check the output above for errors.
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   BUILD SUCCESSFUL!
echo.
echo   Your app folder is at:
echo   %CD%\dist\SupermarketApp\
echo.
echo   To install on another PC:
echo     1. Copy the entire  dist\SupermarketApp\  folder
echo     2. Double-click  SupermarketApp.exe
echo.
echo   The database (supermarket.db) is created next to the .exe
echo   so your data persists between sessions.
echo ============================================================
echo.
pause
