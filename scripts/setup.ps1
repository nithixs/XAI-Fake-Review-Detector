$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory

function Test-ProjectPython([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    try {
        & $Path --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

$venvPython = Join-Path $projectDirectory 'venv/Scripts/python.exe'
if (-not (Test-ProjectPython $venvPython)) {
    # Check Python before replacing a stale environment, so a missing interpreter
    # never turns into a confusing partial installation.
    try {
        & py -3.11 --version *> $null
    } catch {
        throw 'Python 3.11 is required. Install it from python.org, then run this setup script again.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required. Install it from python.org, then run this setup script again.' }
    if (Test-Path -LiteralPath 'venv') { Remove-Item -LiteralPath 'venv' -Recurse -Force }
    & py -3.11 -m venv venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python 3.11 environment.' }
}
& $venvPython -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
Push-Location frontend
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'Setup complete. Run: powershell -ExecutionPolicy Bypass -File scripts/start.ps1' -ForegroundColor Green
