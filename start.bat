@echo off
setlocal
cd /d "%~dp0"
set "PET_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PET_PYTHON=.venv\Scripts\python.exe"
"%PET_PYTHON%" tools\check_assets.py
if errorlevel 1 (
    pause
    exit /b 1
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "pet\nailong_pet.py"
    exit /b 0
)
where pythonw.exe >nul 2>nul
if not errorlevel 1 (
    start "" pythonw.exe "pet\nailong_pet.py"
    exit /b 0
)
echo Python was not found. Follow the setup steps in README.md.
pause
exit /b 1
