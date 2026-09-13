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
    throw "端口 $Port 已被占用，拒绝把已有进程误判为发布包启动成功。"
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
      throw "便携版发布包在健康检查前退出，退出码：$($process.ExitCode)"
    }
    try {
      $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
    } catch {
      Start-Sleep -Milliseconds 500
    }
  } while (-not $health -and (Get-Date) -lt $deadline)

  if (-not $health -or $health.status -ne 'ok') {
    throw '便携版发布包健康检查失败或超时。'
  }
  if ($health.version -ne $expectedVersion) {
    throw "便携版程序版本不一致：期望 $expectedVersion，实际 $($health.version)"
  }

  $version = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/version" -TimeoutSec 5
  if ($version.version -ne $expectedVersion -or $version.content_version -ne $expectedContentVersion) {
    throw "便携版版本元数据不一致：程序=$($version.version)，内容=$($version.content_version)"
  }
  $content = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/content/version" -TimeoutSec 5
  if ($content.content_version -ne $expectedContentVersion -or $content.schema_version -lt 1 -or $content.counts.questions -lt 0) {
    throw "便携版内容元数据无效：Schema=$($content.schema_version)"
  }
  $startup = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/startup" -TimeoutSec 5
  if (-not $startup.active_profile -or $startup.paper_count -lt 0 -or $startup.question_count -lt 0) {
    throw "便携版首页启动数据无效：未返回 active_profile 或题库计数。"
  }
  Write-Output ("Windows portable smoke passed: version={0}, content={1}, schema={2}" -f $version.version, $version.content_version, $content.schema_version)
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
