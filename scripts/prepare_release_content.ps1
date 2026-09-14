[CmdletBinding()]
param(
  [string]$BundlePath = $env:EPM_RELEASE_CONTENT_BUNDLE_PATH,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($BundlePath)) {
  & (Join-Path $PSScriptRoot 'require_release_content.ps1')
  exit $LASTEXITCODE
}

$arguments = @(
  (Join-Path $projectRoot 'tools\prepare_release_content_bundle.py'),
  '--bundle',
  $BundlePath
)
if ($Force) {
  $arguments += '--force'
}
& python @arguments
if ($LASTEXITCODE -ne 0) {
  throw "发布内容 bundle 安装失败，退出码：$LASTEXITCODE"
}

& (Join-Path $PSScriptRoot 'require_release_content.ps1')
exit $LASTEXITCODE
