$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment not found. Run setup.ps1 first."
}

$corepack = Get-Command "corepack.cmd" -ErrorAction SilentlyContinue
if (-not $corepack) {
    $corepack = Get-Command "corepack.exe" -ErrorAction SilentlyContinue
}
if (-not $corepack) {
    throw "Node.js with Corepack is required. Run setup.ps1 after installing Node.js."
}

$backend = Start-Process `
    -FilePath $python `
    -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8765", "--reload" `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -PassThru

try {
    Push-Location (Join-Path $PSScriptRoot "frontend")
    try {
        & $corepack.Source pnpm run dev
    }
    finally {
        Pop-Location
    }
}
finally {
    if (-not $backend.HasExited) {
        Stop-Process -Id $backend.Id
    }
}
