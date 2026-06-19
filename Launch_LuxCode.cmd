@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m luxcode_desktop.main
) else (
  echo LuxCode virtual environment was not found.
  pause
)
