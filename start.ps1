$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$launcher = Join-Path $projectRoot "run_app.py"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Run setup.ps1 first."
    exit 1
}

Set-Location -LiteralPath $projectRoot
& $python $launcher
