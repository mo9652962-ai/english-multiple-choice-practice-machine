$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not (Test-Path -LiteralPath ".venv")) {
    $py = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3.12 -m venv .venv
    }
    else {
        $python = Get-Command "python.exe" -ErrorAction SilentlyContinue
        if (-not $python) {
            throw "Python 3.12 is required. Install Python and run setup.ps1 again."
        }
        & $python.Source -m venv .venv
    }
}

& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

$corepack = Get-Command "corepack.cmd" -ErrorAction SilentlyContinue
if (-not $corepack) {
    $corepack = Get-Command "corepack.exe" -ErrorAction SilentlyContinue
}
if (-not $corepack) {
    throw "Node.js with Corepack is required. Install Node.js and run setup.ps1 again."
}

Push-Location frontend
try {
    & $corepack.Source pnpm install --frozen-lockfile
    & $corepack.Source pnpm run build
}
finally {
    Pop-Location
}

Write-Host "Setup complete. Run start.ps1 to launch English Practice Machine."
