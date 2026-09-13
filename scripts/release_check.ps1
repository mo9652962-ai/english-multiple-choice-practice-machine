param(
  [switch]$MetadataOnly,
  [switch]$RequireAndroidMetadata,
  [switch]$RequireMatchingContent,
  [switch]$StrictQuality,
  [switch]$RequirePackageProvenance,
  [switch]$RequirePublishableProvenance,
  [int]$MinVocabulary = 0,
  [int]$MinSchemaVersion = 0,
  [switch]$CheckTemplates,
  [string[]]$Artifact = @(),
  [string]$WriteReport = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = $null
$uv = $null
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
  $python = $venvPython
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $python = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  $python = "python"
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
  $uv = "uv"
} else {
  throw "未找到 Python 或 uv。请先按 README 创建 .venv，或安装 Python 3.11+。"
}

$scriptArgs = @((Join-Path $projectRoot "tools\release_check.py"))
if ($MetadataOnly) { $scriptArgs += "--metadata-only" }
if ($RequireAndroidMetadata) { $scriptArgs += "--require-android-metadata" }
if ($RequireMatchingContent) { $scriptArgs += "--require-matching-content" }
if ($StrictQuality) { $scriptArgs += "--strict-quality" }
if ($RequirePackageProvenance) { $scriptArgs += "--require-package-provenance" }
if ($RequirePublishableProvenance) { $scriptArgs += "--require-publishable-provenance" }
if ($MinVocabulary -gt 0) { $scriptArgs += @("--min-vocabulary", $MinVocabulary.ToString()) }
if ($MinSchemaVersion -gt 0) { $scriptArgs += @("--min-schema-version", $MinSchemaVersion.ToString()) }
if ($CheckTemplates) { $scriptArgs += "--check-templates" }
foreach ($artifactPath in $Artifact) {
  if ($artifactPath) { $scriptArgs += @("--artifact", $artifactPath) }
}
if ($WriteReport) { $scriptArgs += @("--write-report", $WriteReport) }

if ($uv) {
  $uvArgs = @("run", "--with-requirements", (Join-Path $projectRoot "requirements-dev.txt"), "python") + $scriptArgs
  & $uv @uvArgs
} else {
  & $python @scriptArgs
}
exit $LASTEXITCODE
