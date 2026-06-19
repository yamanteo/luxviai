@echo off
cd /d "%~dp0"
set "LUXCODE_DESKTOP_BUILD=Guncel UI 2026-06-18 kalici runtime"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m luxcode_desktop.main
    exit /b 0
)

echo LuxCode sanal Python ortami bulunamadi.
pause
exit /b 1
