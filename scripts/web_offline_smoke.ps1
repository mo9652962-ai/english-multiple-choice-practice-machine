[CmdletBinding()]
param(
  [string]$Dist = "$(Join-Path (Split-Path -Parent $PSScriptRoot) 'frontend\dist')",
  [int]$Port = 18768,
  [int]$TimeoutSeconds = 45,
  [string]$Python = 'python.exe',
  [string]$Chrome = '',
  [string]$Node = 'node.exe'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$resolvedDist = (Resolve-Path -LiteralPath $Dist -ErrorAction Stop).Path
$pythonCommand = Get-Command $Python -ErrorAction Stop
$chromeCommand = $null
if ($Chrome) {
  $chromeCommand = (Resolve-Path -LiteralPath $Chrome -ErrorAction Stop).Path
} else {
  $chromeCommand = (Get-Command chrome.exe -ErrorAction SilentlyContinue).Source
  if (-not $chromeCommand) {
    $candidates = @(
      'C:\Program Files\Google\Chrome\Application\chrome.exe',
      'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
    )
    $chromeCommand = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
  }
}
if (-not $chromeCommand) { throw 'Chrome 未找到，无法执行浏览器级离线烟测。' }

$smokeRoot = Join-Path $env:TEMP ("epm-web-offline-smoke-" + [guid]::NewGuid().ToString('N'))
$profileDir = Join-Path $smokeRoot 'chrome-profile'
$domPath = Join-Path $smokeRoot 'dom.html'
$serverOut = Join-Path $smokeRoot 'server.out'
$serverErr = Join-Path $smokeRoot 'server.err'
$chromeErr = Join-Path $smokeRoot 'chrome.err'
$serverProcess = $null
$chromeProcess = $null
$cdpPort = $Port + 1

New-Item -ItemType Directory -Path $smokeRoot,$profileDir -Force | Out-Null
try {
  $serverProcess = Start-Process -FilePath $pythonCommand.Source -ArgumentList @('-m','http.server',[string]$Port,'--bind','127.0.0.1') -WorkingDirectory $resolvedDist -RedirectStandardOutput $serverOut -RedirectStandardError $serverErr -PassThru -WindowStyle Hidden
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $ready = $false
  do {
    if ($serverProcess.HasExited) { throw "静态 Web 服务提前退出，退出码：$($serverProcess.ExitCode)" }
    try {
      $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -TimeoutSec 3 -UseBasicParsing
      if ($response.StatusCode -eq 200) { $ready = $true }
    } catch { Start-Sleep -Milliseconds 500 }
  } while (-not $ready -and (Get-Date) -lt $deadline)
  if (-not $ready) { throw '静态 Web 服务启动超时。' }

  $chromeArgs = @(
    '--headless=new', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage',
    "--remote-debugging-port=$cdpPort", "--user-data-dir=$profileDir",
    "http://127.0.0.1:$Port/"
  )
  $chromeProcess = Start-Process -FilePath $chromeCommand -ArgumentList $chromeArgs -RedirectStandardOutput $domPath -RedirectStandardError $chromeErr -PassThru -WindowStyle Hidden
  $cdpReady = $false
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    if ($chromeProcess.HasExited) { throw "Chrome 在 CDP 页面检查前退出，退出码：$($chromeProcess.ExitCode)" }
    try {
      $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$cdpPort/json" -TimeoutSec 3
      if (@($targets | Where-Object { $_.type -eq 'page' -and $_.url -like "http://127.0.0.1:$Port/*" }).Count -gt 0) { $cdpReady = $true }
    } catch { Start-Sleep -Milliseconds 300 }
  } while (-not $cdpReady -and (Get-Date) -lt $deadline)
  if (-not $cdpReady) { throw 'Chrome DevTools 页面目标启动超时。' }
  $nodeCommand = Get-Command $Node -ErrorAction Stop
  & $nodeCommand.Source (Join-Path $projectRoot 'tools\web_offline_cdp_smoke.mjs') --cdp-port $cdpPort --url "http://127.0.0.1:$Port/"
  if ($LASTEXITCODE -ne 0) { throw "浏览器级离线烟测失败，退出码=$LASTEXITCODE。" }
  Write-Output ("Web offline browser smoke passed: profile=考研英语一, dist={0}" -f $resolvedDist)
} finally {
  if ($chromeProcess -and -not $chromeProcess.HasExited) {
    Stop-Process -Id $chromeProcess.Id -Force -ErrorAction SilentlyContinue
  }
  if ($serverProcess -and -not $serverProcess.HasExited) {
    Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
  }
  if (Test-Path -LiteralPath $smokeRoot) {
    Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}
