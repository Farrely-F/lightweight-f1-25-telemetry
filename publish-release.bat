@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM F1 Telemetry Overlay - GitHub Release Publisher
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   F1 25 Telemetry Overlay - Publish to GitHub Releases
echo ============================================================
echo.

REM --- Check for GitHub CLI ---
echo [INFO] Checking for GitHub CLI (gh)...
where gh >nul 2>&1
if errorlevel 1 (
    echo [ERROR] GitHub CLI not found.
    echo.
    echo Please install GitHub CLI from:
    echo   https://cli.github.com/
    echo.
    echo After installation, authenticate with:
    echo   gh auth login
    exit /b 1
)

REM --- Check if authenticated ---
echo [INFO] Checking GitHub authentication...
gh auth status >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Not authenticated with GitHub.
    echo.
    echo Please run:
    echo   gh auth login
    exit /b 1
)

REM --- Set version ---
set "VERSION="
if not "%~1"=="" (
    set "VERSION=%~1"
) else (
    echo Enter version tag (e.g., v1.0.0):
    set /p VERSION="> "
)

if "%VERSION%"=="" (
    echo [ERROR] Version tag is required.
    echo Usage: publish-release.bat [v1.0.0]
    exit /b 1
)

REM Remove 'v' prefix if user added it
set "VERSION_TAG=%VERSION%"
if "%VERSION:~0,1%"=="v" (
    set "VERSION_TAG=%VERSION%"
) else (
    set "VERSION_TAG=v%VERSION%"
)

echo.
echo ============================================================
echo   Release Configuration
echo ============================================================
echo   Version Tag:  %VERSION_TAG%
echo   Installer:    dist\installer\F1TelemetryOverlay-Setup-1.0.0.exe
echo.

REM --- Check if installer exists ---
set "INSTALLER_PATH=dist\installer\F1TelemetryOverlay-Setup-1.0.0.exe"
if not exist "%INSTALLER_PATH%" (
    echo [ERROR] Installer not found: %INSTALLER_PATH%
    echo.
    echo Please run build_windows.bat first to create the installer.
    exit /b 1
)

REM --- Get repo info ---
echo [INFO] Getting repository information...
for /f "tokens=1,2" %%a in ('gh repo view --json name,owner --jq "{name:.name,owner:.owner.login}" 2^nul') do (
    set "REPO_OWNER=%%a"
    set "REPO_NAME=%%b"
)

if "%REPO_NAME%"=="" (
    echo [ERROR] Could not determine repository. Make sure you're in the repo directory.
    exit /b 1
)

echo [INFO] Repository: %REPO_OWNER%/%REPO_NAME%

REM --- Check if tag already exists ---
echo.
echo [INFO] Checking if tag exists...
gh release view %VERSION_TAG% >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Tag %VERSION_TAG% already exists!
    echo.
    set /p "CONFIRM=Overwrite existing release? (y/N): "
    if /i not "%CONFIRM%"=="y" (
        echo [ABORTED] Release cancelled.
        exit /b 1
    )
    echo [INFO] Overwriting existing release...
    gh release delete %VERSION_TAG% --yes >nul 2>&1
    git tag -d %VERSION_TAG% >nul 2>&1
    git push origin :refs/tags/%VERSION_TAG% >nul 2>&1
)

REM --- Get release notes ---
set "RELEASE_NOTES_FILE=%TEMP%\release_notes.txt"
echo [INFO] Opening editor for release notes...
echo Enter release notes below. Save and close to continue, or close without saving to skip." > "%RELEASE_NOTES_FILE%"
echo. >> "%RELEASE_NOTES_FILE%"
echo Changes in %VERSION_TAG%: >> "%RELEASE_NOTES_FILE%"
echo - Bug fixes >> "%RELEASE_NOTES_FILE%"
echo - Performance improvements >> "%RELEASE_NOTES_FILE%"
notepad "%RELEASE_NOTES_FILE%"

REM Ask if user wants to continue
set /p "CONTINUE="Continue with release? (Y/n): ""
if /i "%CONTINUE%"=="n" (
    del "%RELEASE_NOTES_FILE%" 2>nul
    echo [ABORTED] Release cancelled.
    exit /b 0
)

REM --- Create Git tag ---
echo.
echo [STEP 1/4] Creating Git tag...
git tag -a %VERSION_TAG% -m "%VERSION_TAG% Release"
if errorlevel 1 (
    echo [ERROR] Failed to create tag.
    exit /b 1
)
echo [OK] Tag %VERSION_TAG% created.

REM --- Push tag to remote ---
echo.
echo [STEP 2/4] Pushing tag to remote...
git push origin %VERSION_TAG%
if errorlevel 1 (
    echo [ERROR] Failed to push tag.
    exit /b 1
)
echo [OK] Tag pushed to remote.

REM --- Create GitHub release ---
echo.
echo [STEP 3/4] Creating GitHub release...
gh release create %VERSION_TAG% --title "F1 Telemetry Overlay %VERSION_TAG%" --notes-file "%RELEASE_NOTES_FILE%"
if errorlevel 1 (
    echo [ERROR] Failed to create release.
    exit /b 1
)
echo [OK] Release created.

REM --- Upload installer asset ---
echo.
echo [STEP 4/4] Uploading installer asset...
for %%F in ("%INSTALLER_PATH%") do set "INSTALLER_NAME=%%~nxF"
gh release upload %VERSION_TAG% "%INSTALLER_PATH%" --clobber
if errorlevel 1 (
    echo [ERROR] Failed to upload installer.
    exit /b 1
)
echo [OK] Installer uploaded.

REM --- Cleanup ---
del "%RELEASE_NOTES_FILE%" 2>nul

REM --- Get release URL ---
for /f "tokens=4" %%a in ('gh release view %VERSION_TAG% --json url --jq ".url"') do set "RELEASE_URL=%%a"

echo.
echo ============================================================
echo   RELEASE PUBLISHED SUCCESSFULLY!
echo ============================================================
echo.
echo   Version:   %VERSION_TAG%
echo   Release:   %RELEASE_URL%
echo   Installer: %INSTALLER_NAME%
echo.
echo   The installer is now available for download!
echo.

REM --- Open release page ---
set /p "OPEN="Open release page in browser? (Y/n): ""
if /i not "%OPEN%"=="n" (
    start %RELEASE_URL%
)

exit /b 0
