[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$Executable,
  [int]$Port = 18765,
  [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'
$resolvedExecutable = (Resolve-Path -LiteralPath $Executable -ErrorAction Stop).Path
$projectRoot = Split-Path -Parent $PSScriptRoot
$expectedVersion = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()
$expectedContentVersion = (Get-Content -LiteralPath (Join-Path $projectRoot 'CONTENT_VERSION') -Raw).Trim()
$releaseDatabase = Join-Path $projectRoot 'backend\data\question_bank.db'
if (-not (Test-Path -LiteralPath $releaseDatabase)) {
  throw "发布数据库不存在，无法验证 portable 包 seed：$releaseDatabase"
}
$expectedDatabaseHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $releaseDatabase).Hash.ToLowerInvariant()
$smokeRoot = Join-Path $env:TEMP ("epm-portable-smoke-" + [guid]::NewGuid().ToString('N'))
$userDataDir = Join-Path $smokeRoot 'user-data'
$diagnosticLog = Join-Path $smokeRoot 'electron-diagnostic.jsonl'
$process = $null
$previousPort = $env:EPM_PORT
$previousDiagnosticLog = $env:EPM_DIAGNOSTIC_LOG

New-Item -ItemType Directory -Path $userDataDir -Force | Out-Null
try {
  $env:EPM_PORT = [string]$Port
  $env:EPM_DIAGNOSTIC_LOG = $diagnosticLog
  $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
  if ($listeners.Count -gt 0) {
    throw "Port $Port is already in use; refusing to mistake an existing process for the packaged app."
  }

  $arguments = @(
    '--disable-gpu',
    '--no-sandbox',
    "--user-data-dir=$userDataDir"
  )
  $process = Start-Process -FilePath $resolvedExecutable -ArgumentList $arguments -PassThru -WindowStyle Hidden
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $health = $null
  do {
    if ($process.HasExited) {
      throw "Portable package exited before health check; exit code: $($process.ExitCode)"
    }
    try {
      $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
    } catch {
      Start-Sleep -Milliseconds 500
    }
  } while (-not $health -and (Get-Date) -lt $deadline)

  if (-not $health -or $health.status -ne 'ok') {
    throw 'Portable package health check failed or timed out.'
  }
  if ($health.version -ne $expectedVersion) {
    throw "Portable app version mismatch: expected $expectedVersion, actual $($health.version)"
  }

  $version = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/version" -TimeoutSec 5
  if ($version.version -ne $expectedVersion -or $version.content_version -ne $expectedContentVersion) {
    throw "Portable version metadata mismatch: app=$($version.version), content=$($version.content_version)"
  }
  $content = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/content/version" -TimeoutSec 5
  if ($content.content_version -ne $expectedContentVersion -or $content.schema_version -lt 1 -or $content.counts.questions -lt 0) {
    throw "Portable content metadata is invalid: schema=$($content.schema_version)"
  }
  $resourcePath = $null
  if (Test-Path -LiteralPath $diagnosticLog) {
    foreach ($line in (Get-Content -LiteralPath $diagnosticLog)) {
      try {
        $event = $line | ConvertFrom-Json
        if ($event.resourcesPath) {
          $resourcePath = [string]$event.resourcesPath
          break
        }
      } catch {
        # Ignore a partially flushed diagnostic line and keep polling evidence.
      }
    }
  }
  if ([string]::IsNullOrWhiteSpace($resourcePath)) {
    throw 'Portable diagnostic log did not provide resourcesPath; packaged seed cannot be verified.'
  }
  $packagedSeed = Join-Path $resourcePath 'seed\question_bank.db'
  if (-not (Test-Path -LiteralPath $packagedSeed)) {
    throw "Packaged seed is missing: $packagedSeed"
  }
  $actualPackagedSeedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $packagedSeed).Hash.ToLowerInvariant()
  if ($actualPackagedSeedHash -ne $expectedDatabaseHash) {
    throw "Packaged seed hash mismatch: expected $expectedDatabaseHash, actual $actualPackagedSeedHash"
  }
  $startup = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/startup" -TimeoutSec 5
  if (-not $startup.active_profile -or $startup.paper_count -lt 0 -or $startup.question_count -lt 0) {
    throw "Portable startup payload is invalid: active_profile or paper/question counts are missing."
  }
  Write-Output ("Windows portable smoke passed: version={0}, content={1}, schema={2}, seed={3}" -f $version.version, $version.content_version, $content.schema_version, $actualPackagedSeedHash)
} finally {
  if (Test-Path -LiteralPath $diagnosticLog) {
    Write-Output "Electron diagnostic log: $diagnosticLog"
    Get-Content -LiteralPath $diagnosticLog
  }
  if ($process -and -not $process.HasExited) {
    & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
    $null = $process.WaitForExit(10000)
  }
  if ($null -eq $previousPort) { Remove-Item Env:EPM_PORT -ErrorAction SilentlyContinue } else { $env:EPM_PORT = $previousPort }
  if ($null -eq $previousDiagnosticLog) { Remove-Item Env:EPM_DIAGNOSTIC_LOG -ErrorAction SilentlyContinue } else { $env:EPM_DIAGNOSTIC_LOG = $previousDiagnosticLog }
  if (Test-Path -LiteralPath $smokeRoot) {
    Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}
