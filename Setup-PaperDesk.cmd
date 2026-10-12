@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
echo Setting up PaperDesk...
if not exist ".venv\Scripts\python.exe" (
  if defined PAPERDESK_PYTHON (
    "%PAPERDESK_PYTHON%" -m venv .venv
  ) else (
    py -3.12 -m venv .venv >nul 2>nul
    if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv >nul 2>nul
    if not exist ".venv\Scripts\python.exe" python -m venv .venv
  )
)
if not exist ".venv\Scripts\python.exe" goto fail
".venv\Scripts\python.exe" scripts\check_environment.py || goto fail
node -e "if(Number(process.versions.node.split('.')[0]) < 20) process.exit(1)" || goto fail
".venv\Scripts\python.exe" -m pip install --require-hashes --only-binary=:all: -r requirements-hashed.txt || goto fail
where npm.cmd >nul 2>nul
if errorlevel 1 (
  echo Node.js and npm are required to install the project-local Codex CLI.
  goto fail
)
if not exist ".tools\codex" mkdir ".tools\codex"
copy /y "scripts\codex\package.json" ".tools\codex\package.json" >nul || goto fail
copy /y "scripts\codex\package-lock.json" ".tools\codex\package-lock.json" >nul || goto fail
call npm.cmd ci --prefix .tools\codex --ignore-scripts --no-audit --no-fund || goto fail
".venv\Scripts\python.exe" scripts\check_environment.py --cli || goto fail
echo PaperDesk setup complete. Run start.cmd to open the workbench.
exit /b 0
:fail
echo Setup failed. Use Windows x64, Python 3.12 and Node.js 20+; check the messages above.
if not defined PAPERDESK_NONINTERACTIVE pause
exit /b 1
