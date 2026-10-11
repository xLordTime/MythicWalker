$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe -m pip install pyinstaller==6.16.0
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller konnte nicht installiert werden.' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name MythicWalker --icon assets/mythicwalker.ico --add-data 'assets;assets' --collect-submodules wizwalker --add-data 'web;web' --add-data 'release_source.json;.' --exclude-module tkinter --exclude-module PyQt6 --exclude-module PySide6 --exclude-module matplotlib --exclude-module numpy desktop.py
if ($LASTEXITCODE -ne 0) { throw 'EXE-Build fehlgeschlagen.' }
& .\.venv\Scripts\python.exe ..\scripts\release_manifest.py dist\MythicWalker.exe
Write-Host 'EXE: bridge\dist\MythicWalker.exe. Browserstart, automatische Kopplung und Status-Widget sind integriert.'
