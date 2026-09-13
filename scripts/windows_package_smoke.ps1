param(
  [string]$Executable = "backend\dist\backend_app\backend_app.exe",
  [int]$Port = 18765,
  [int]$TimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"
$resolvedExecutable = (Resolve-Path -LiteralPath $Executable -ErrorAction Stop).Path
$projectRoot = Split-Path -Parent $PSScriptRoot
$expectedVersion = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()
$expectedContentVersion = (Get-Content -LiteralPath (Join-Path $projectRoot 'CONTENT_VERSION') -Raw).Trim()
$smokeRoot = Join-Path $env:TEMP ("epm-package-smoke-" + [guid]::NewGuid().ToString("N"))
$dataDir = Join-Path $smokeRoot "data"
$process = $null

New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
$previousDataDir = $env:EPM_DATA_DIR
$previousPort = $env:EPM_PORT
try {
  $env:EPM_DATA_DIR = $dataDir
  $env:EPM_PORT = [string]$Port
  $process = Start-Process -FilePath $resolvedExecutable -WorkingDirectory (Split-Path -Parent $resolvedExecutable) -PassThru -WindowStyle Hidden
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $health = $null
  do {
    if ($process.HasExited) {
      throw "backend_app.exe 在健康检查前退出，退出码：$($process.ExitCode)"
    }
    try {
      $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
    } catch {
      Start-Sleep -Milliseconds 500
    }
  } while (-not $health -and (Get-Date) -lt $deadline)

  if (-not $health -or $health.status -ne "ok") {
    throw "backend_app.exe 健康检查失败或超时。"
  }
  if ($health.version -ne $expectedVersion) {
    throw "Windows 包版本不一致：期望 $expectedVersion，实际 $($health.version)"
  }
  $version = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/version" -TimeoutSec 5
  if ($version.version -ne $expectedVersion -or $version.content_version -ne $expectedContentVersion) {
    throw "Windows 包版本元数据不一致：程序=$($version.version)，内容=$($version.content_version)"
  }
  $content = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/content/version" -TimeoutSec 5
  if ($content.schema_version -lt 1 -or $content.counts.questions -lt 0) {
    throw "Windows 包内容元数据无效：Schema=$($content.schema_version)"
  }
  $startup = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/startup" -TimeoutSec 5
  if (-not $startup.active_profile -or $startup.paper_count -lt 0 -or $startup.question_count -lt 0) {
    throw "Windows 包首页启动数据无效：未返回 active_profile 或题库计数。"
  }
  Write-Output ("Windows package smoke passed: version={0}, content={1}, schema={2}, database={3}" -f $version.version, $version.content_version, $content.schema_version, $health.database)
} finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    $null = $process.WaitForExit(5000)
  }
  if ($null -eq $previousDataDir) { Remove-Item Env:EPM_DATA_DIR -ErrorAction SilentlyContinue } else { $env:EPM_DATA_DIR = $previousDataDir }
  if ($null -eq $previousPort) { Remove-Item Env:EPM_PORT -ErrorAction SilentlyContinue } else { $env:EPM_PORT = $previousPort }
  if (Test-Path -LiteralPath $smokeRoot) {
    Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}
