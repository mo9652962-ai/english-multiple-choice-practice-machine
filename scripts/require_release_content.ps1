[CmdletBinding()]
param(
  [string]$ReleaseDatabase = 'backend\data\question_bank.db',
  [string]$OfflineDatabase = 'frontend\public\question_bank.db'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$required = @(
  (Join-Path $projectRoot $ReleaseDatabase),
  (Join-Path $projectRoot $OfflineDatabase)
)

foreach ($path in $required) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "发布内容输入缺失：$path。clean checkout 不会自动生成正式题库；请先注入经过核验的 release/offline seed，再运行发布流程。"
  }
  $item = Get-Item -LiteralPath $path
  if ($item.Length -le 0) {
    throw "发布内容输入为空：$path"
  }
  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
  Write-Output ("Release content input verified: path={0}, size={1}, sha256={2}" -f $path, $item.Length, $hash)
}
