@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Zuerst Setup.ps1 ausfuehren oder die fertige MythicWalker.exe verwenden.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" desktop.py
