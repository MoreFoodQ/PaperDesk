@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set EASYREAD_HOME=%CD%\data
if not exist ".venv\Scripts\pythonw.exe" (
  call Setup-PaperDesk.cmd
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" scripts\check_environment.py --cli >nul 2>nul
if errorlevel 1 (
  call Setup-PaperDesk.cmd
  if errorlevel 1 exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m easyread serve --open --exit-on-close
exit /b 0
