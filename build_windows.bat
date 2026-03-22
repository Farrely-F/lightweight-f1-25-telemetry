@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM F1 Telemetry Overlay - Windows Build Helper (PyInstaller)
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   F1 Telemetry Overlay - Build Windows EXE
echo ============================================================
echo.

REM --- Validate Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not available in PATH.
    echo Install Python 3.10+ and retry.
    exit /b 1
)

REM --- Create virtual environment if missing ---
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
) else (
    echo [INFO] Using existing virtual environment: .venv
)

REM --- Upgrade packaging tools ---
echo [INFO] Upgrading pip/setuptools/wheel ...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [ERROR] Failed to upgrade packaging tools.
    exit /b 1
)

REM --- Install dependencies from requirements-dev ---
echo [INFO] Installing dependencies from requirements-dev.txt ...
call ".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies from requirements-dev.txt.
    exit /b 1
)

REM --- Clean previous outputs ---
if exist "build" (
    echo [INFO] Removing old build folder ...
    rmdir /s /q "build"
)
if exist "dist" (
    echo [INFO] Removing old dist folder ...
    rmdir /s /q "dist"
)
if exist "f1-telemetry-overlay.spec" (
    echo [INFO] Removing old spec file ...
    del /q "f1-telemetry-overlay.spec"
)

REM --- Build executable ---
echo [INFO] Building one-file windowed executable...
call ".venv\Scripts\python.exe" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "f1-telemetry-overlay" ^
  --icon "fto-icon.ico" ^
  --add-data "fto-icon.ico;." ^
  "main.py"

if errorlevel 1 (
    echo [ERROR] Build failed.
    exit /b 1
)

echo.
echo [SUCCESS] Build complete.
echo Output EXE:
echo   %CD%\dist\f1-telemetry-overlay.exe
echo.
echo You can run it directly, or distribute the EXE from the dist folder.
echo.
exit /b 0
