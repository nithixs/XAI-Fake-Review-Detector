$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$pythonCommand = Join-Path (Get-Location) 'venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonCommand)) {
    throw 'Run scripts/setup.ps1 first to install the project.'
}
try {
    & $pythonCommand --version *> $null
} catch {
    throw 'The local Python environment is no longer usable. Run scripts/setup.ps1 to rebuild it.'
}
if ($LASTEXITCODE -ne 0) { throw 'The local Python environment is no longer usable. Run scripts/setup.ps1 to rebuild it.' }
& $pythonCommand -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
Push-Location frontend
try {
    & npm.cmd run lint
    if ($LASTEXITCODE -ne 0) { throw 'Frontend lint failed.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
