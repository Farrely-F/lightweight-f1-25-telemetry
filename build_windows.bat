@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM F1 Telemetry Overlay - Windows Build Helper
REM ============================================================

cd /d "%~dp0"

REM --- Check for admin privileges (needed for installer) ---
net session >nul 2>&1
set "IS_ADMIN=%errorlevel%"

echo.
echo ============================================================
echo   F1 25 Telemetry Overlay - Build & Installer
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
echo.
echo [STEP 1/3] Building PyInstaller executable...
echo ============================================================
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
echo [STEP 2/3] Verifying built executable...
echo ============================================================
if not exist "dist\f1-telemetry-overlay.exe" (
    echo [ERROR] Executable not found at dist\f1-telemetry-overlay.exe
    exit /b 1
)
echo [OK] Executable found.

REM --- Copy icon to dist for installer ---
copy /Y "fto-icon.ico" "dist\fto-icon.ico" >nul

REM --- Build installer ---
echo.
echo [STEP 3/3] Building Windows installer...
echo ============================================================

REM --- Check for Inno Setup ---
set "ISCC_PATH="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "%ISCC_PATH%"=="" (
    echo.
    echo [WARNING] Inno Setup 6 not found.
    echo.
    echo Please install Inno Setup 6 from:
    echo   https://jrsoftware.org/isdl.php
    echo.
    echo Installation complete. EXE located at:
    echo   %CD%\dist\f1-telemetry-overlay.exe
    echo.
    echo To create installer, install Inno Setup 6 and run:
    echo   "%~dp0build_windows.bat"
    echo.
    exit /b 0
)

REM --- Create output directory for installer ---
if not exist "dist\installer" mkdir "dist\installer"

REM --- Build the installer ---
echo [INFO] Running Inno Setup compiler...
"%ISCC_PATH%" "f1-telemetry-overlay.iss"

if errorlevel 1 (
    echo [ERROR] Installer build failed.
    exit /b 1
)

echo.
echo ============================================================
echo   BUILD COMPLETE
echo ============================================================
echo.
echo Executable:
echo   %CD%\dist\f1-telemetry-overlay.exe
echo.
echo Installer:
echo   %CD%\dist\installer\F1TelemetryOverlay-Setup-1.0.0.exe
echo.
echo Distribution files:
echo   - dist\f1-telemetry-overlay.exe  (portable EXE)
echo   - dist\installer\*.exe            (installer)
echo.
echo NOTE: If you plan to distribute:
echo   - Use the installer for end-users (handles shortcuts, uninstall)
echo   - Use the portable EXE for testing/direct distribution
echo.
exit /b 0
