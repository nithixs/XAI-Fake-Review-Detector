param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory
$pythonCommand = Join-Path $projectDirectory 'venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonCommand)) {
    throw 'Run scripts/setup.ps1 first to install the project.'
}
try {
    & $pythonCommand --version *> $null
} catch {
    throw 'The local Python environment is no longer usable. Run scripts/setup.ps1 to rebuild it.'
}
if ($LASTEXITCODE -ne 0) { throw 'The local Python environment is no longer usable. Run scripts/setup.ps1 to rebuild it.' }
$buildIndex = Join-Path $projectDirectory 'frontend/dist/index.html'
$needsBuild = -not (Test-Path -LiteralPath $buildIndex)
if (-not $needsBuild) {
    $buildTime = (Get-Item -LiteralPath $buildIndex).LastWriteTimeUtc
    $frontendInputs = @(Get-ChildItem -LiteralPath 'frontend/src', 'frontend/public' -Recurse -File)
    $frontendInputs += Get-Item -LiteralPath 'frontend/index.html', 'frontend/package.json', 'frontend/package-lock.json', 'frontend/vite.config.js'
    $needsBuild = @($frontendInputs | Where-Object { $_.LastWriteTimeUtc -gt $buildTime }).Count -gt 0
}
if ($needsBuild) {
    Write-Host 'Building the latest frontend changes...' -ForegroundColor Cyan
    Push-Location frontend
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
Write-Host "ReviewGuard: http://127.0.0.1:$Port" -ForegroundColor Cyan
Write-Host "API documentation: http://127.0.0.1:$Port/docs"
Write-Host 'Press Ctrl+C to stop. First startup seeds the demo database.'
& $pythonCommand -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
