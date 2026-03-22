# F1 25 Telemetry Overlay - Installer Build Guide

This document describes how to build the Windows installer for the F1 25 Telemetry Overlay application.

## Prerequisites

### 1. Python 3.10+
Download from https://www.python.org/downloads/

### 2. Inno Setup 6
Download from https://jrsoftware.org/isdl.php

Inno Setup is used to create the Windows installer (.exe) that handles:
- Desktop and Start Menu shortcuts
- Uninstaller registration
- File installation with proper directory structure

## Quick Build

Run the build script:

```cmd
build_windows.bat
```

This will:
1. Build the PyInstaller executable
2. Create the Windows installer

## Build Output

After a successful build, you'll find:

| File | Description |
|------|-------------|
| `dist\f1-telemetry-overlay.exe` | Portable executable (no installation needed) |
| `dist\installer\F1TelemetryOverlay-Setup-1.0.0.exe` | Windows installer |

## Installing the Installer

1. Run `F1TelemetryOverlay-Setup-1.0.0.exe`
2. Follow the installation wizard
3. Choose whether to create:
   - **Desktop shortcut** - Quick access from desktop
   - **Start with Windows** - Auto-start when you log in

## Uninstallation

Use Windows Settings > Apps > F1 25 Telemetry Overlay > Uninstall

Or run the uninstaller from the Start Menu folder.

## Manual Build Steps

If you need more control, you can build manually:

### Step 1: Build PyInstaller Executable

```cmd
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name "f1-telemetry-overlay" --icon "fto-icon.ico" --add-data "fto-icon.ico;." main.py
```

### Step 2: Create Installer

```cmd
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" f1-telemetry-overlay.iss
```

## Customizing the Installer

Edit `f1-telemetry-overlay.iss` to change:

| Setting | Location | Description |
|---------|----------|-------------|
| Version | Line 3 | `MyAppVersion` |
| Publisher | Line 4 | `MyAppPublisher` |
| Install directory | `[Setup]` section | `DefaultDirName` |
| Installer name | Line 20 | `OutputBaseFilename` |

## Troubleshooting

### "Inno Setup 6 not found"
Install Inno Setup 6 from https://jrsoftware.org/isdl.php

The build script searches these locations:
- `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`
- `C:\Program Files\Inno Setup 6\ISCC.exe`

### Build fails with PyInstaller
See `requirements-dev.txt` contains all necessary dependencies.

### Icon not showing
The icon is embedded in the executable. If it doesn't appear:
1. Refresh desktop icon cache: `taskkill /f /im explorer.exe && start explorer`
2. Or log out and log back in

## Directory Structure

```
telemetry-f1/
├── main.py                      # Application source
├── fto-icon.ico                 # Application icon
├── f1-telemetry-overlay.spec    # PyInstaller spec
├── f1-telemetry-overlay.iss    # Inno Setup installer script
├── build_windows.bat            # Build automation script
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # Build dependencies
└── dist/                        # Build output
    ├── f1-telemetry-overlay.exe       # Portable executable
    ├── fto-icon.ico                    # Icon (for installer)
    └── installer/
        └── F1TelemetryOverlay-Setup-1.0.0.exe  # Windows installer
```

## Distribution

For end-users, distribute the **installer** (`F1TelemetryOverlay-Setup-1.0.0.exe`) rather than the portable executable. The installer:
- Handles installation properly
- Creates shortcuts
- Registers uninstaller
- Allows clean removal