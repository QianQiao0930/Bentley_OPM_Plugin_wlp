@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_new_version.ps1"
if errorlevel 1 (
    echo Update failed. Close OpenPlant Modeler and try again.
) else (
    echo Update complete. Restart OpenPlant Modeler.
)
pause
