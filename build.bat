@echo off
setlocal
cd /d "%~dp0"
set "PET_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PET_PYTHON=.venv\Scripts\python.exe"
"%PET_PYTHON%" tools\check_assets.py
if errorlevel 1 goto :failed
"%PET_PYTHON%" -m PyInstaller --noconfirm --clean NailongPet.spec
if errorlevel 1 goto :failed
echo Built: dist\NailongPet.exe
pause
exit /b 0
:failed
echo Build failed. Check the messages above and README.md.
pause
exit /b 1
