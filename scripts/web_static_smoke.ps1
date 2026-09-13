[CmdletBinding()]
param(
  [string]$Dist = "$(Join-Path (Split-Path -Parent $PSScriptRoot) 'frontend\dist')",
  [int]$Port = 18767,
  [int]$TimeoutSeconds = 45
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
$resolvedDist = (Resolve-Path -LiteralPath $Dist -ErrorAction Stop).Path
$expectedVersion = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()
$npx = Get-Command npx.cmd -ErrorAction SilentlyContinue
if (-not $npx) {
  $npx = Get-Command npx -ErrorAction Stop
}
$process = $null

try {
  $arguments = @(
    'vite', 'preview',
    '--configLoader', 'runner',
    '--host', '127.0.0.1',
    '--port', [string]$Port,
    '--strictPort',
    '--outDir', $resolvedDist
  )
  $process = Start-Process -FilePath $npx.Source -ArgumentList $arguments -WorkingDirectory $frontendRoot -PassThru -WindowStyle Hidden
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $ready = $false
  do {
    if ($process.HasExited) {
      throw "Vite preview 在 smoke 检查前退出，退出码：$($process.ExitCode)"
    }
    try {
      $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -TimeoutSec 3 -UseBasicParsing
      if ($response.StatusCode -eq 200) { $ready = $true }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  } while (-not $ready -and (Get-Date) -lt $deadline)

  if (-not $ready) { throw "Vite preview 启动超时。" }

  $paths = @(
    '/',
    '/release-metadata.json',
    '/question_bank.db',
    '/offline_migrations.json',
    '/manifest.json',
    '/sql-wasm.wasm'
  )
  foreach ($path in $paths) {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port$path" -TimeoutSec 5 -UseBasicParsing
    $contentLength = [int64]$response.Content.Length
    if ($response.StatusCode -ne 200 -or $contentLength -le 0) {
      throw "Web dist 资源检查失败：$path，状态=$($response.StatusCode)，长度=$contentLength"
    }
  }

  $metadata = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/release-metadata.json" -TimeoutSec 5
  if ($metadata.metadata.version -ne $expectedVersion) {
    throw "Web dist 程序版本元数据不一致。"
  }
  if ([string]::IsNullOrWhiteSpace($metadata.metadata.content_version) -or
      [string]::IsNullOrWhiteSpace($metadata.metadata.offline_seed_version)) {
    throw "Web dist 内容版本元数据缺失。"
  }
  Write-Output ("Web static smoke passed: version={0}, content={1}, dist={2}" -f $metadata.metadata.version, $metadata.metadata.content_version, $resolvedDist)
} finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    $null = $process.WaitForExit(5000)
  }
}
