$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $desktopRoot
try {
    $env:PYTHONUTF8 = '1'
    $env:CSC_IDENTITY_AUTO_DISCOVERY = 'false'
    $desktopPython = Join-Path $desktopRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $desktopPython)) { throw 'Run Setup-PaperDesk.cmd first.' }
    $desktopCli = Join-Path $desktopRoot '.tools\codex'
    New-Item -ItemType Directory -Force -Path $desktopCli | Out-Null
    Copy-Item -LiteralPath 'scripts\codex\package.json' -Destination (Join-Path $desktopCli 'package.json')
    Copy-Item -LiteralPath 'scripts\codex\package-lock.json' -Destination (Join-Path $desktopCli 'package-lock.json')
    & npm.cmd ci --prefix $desktopCli --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Pinned official CLI installation failed.' }
    & $desktopPython scripts/check_environment.py --cli
    if ($LASTEXITCODE -ne 0) { throw 'Source environment check failed.' }
    & $desktopPython -m pip install --require-hashes --only-binary=:all: -r requirements-build-hashed.txt
    if ($LASTEXITCODE -ne 0) { throw 'Build tool installation failed.' }
    & npm.cmd ci --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
    & npm.cmd audit
    if ($LASTEXITCODE -ne 0) { throw 'Resolve npm advisories before building.' }
    & $desktopPython scripts/prepare_source_release.py --check-only
    if ($LASTEXITCODE -ne 0) { throw 'Source privacy check failed.' }
    & $desktopPython scripts/prepare_desktop_runtime.py
    if ($LASTEXITCODE -ne 0) { throw 'CLI runtime staging failed.' }
    $env:PYTHONPATH = $desktopRoot
    & $desktopPython scripts/build_backend.py
    if ($LASTEXITCODE -ne 0) { throw 'Backend build failed.' }
    & .\node_modules\.bin\electron-builder.cmd --win nsis --x64 --publish never
    if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
    Write-Host 'Built Windows installer in dist\electron. Run packaged validation before publishing.'
} finally {
    Pop-Location
}
