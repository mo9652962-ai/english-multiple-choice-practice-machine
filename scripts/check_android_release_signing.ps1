[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$KeystorePath,
    [string]$Alias = "",
    [switch]$RequireCiVariables
)

# Safe local preflight for Android release signing.
# It validates the keystore and alias without printing any secret value.
$ErrorActionPreference = "Stop"

function Require-EnvironmentValue([string]$Name) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required environment variable: $Name"
    }
    return $value
}

$resolvedKeystore = (Resolve-Path -LiteralPath $KeystorePath -ErrorAction Stop).Path
$storePassword = [Environment]::GetEnvironmentVariable("EPM_ANDROID_KEYSTORE_PASSWORD")
if ([string]::IsNullOrWhiteSpace($storePassword)) {
    $storePassword = Require-EnvironmentValue "ANDROID_KEYSTORE_PASSWORD"
}

if ([string]::IsNullOrWhiteSpace($Alias)) {
    $Alias = [Environment]::GetEnvironmentVariable("EPM_ANDROID_KEY_ALIAS")
}
if ([string]::IsNullOrWhiteSpace($Alias)) {
    $Alias = Require-EnvironmentValue "ANDROID_KEY_ALIAS"
}

# The key password is checked for presence here; keytool -list validates the
# store password and alias without exposing either password in process output.
$keyPassword = [Environment]::GetEnvironmentVariable("EPM_ANDROID_KEY_PASSWORD")
if ([string]::IsNullOrWhiteSpace($keyPassword)) {
    $keyPassword = Require-EnvironmentValue "ANDROID_KEY_PASSWORD"
}

if ($RequireCiVariables) {
    Require-EnvironmentValue "ANDROID_KEYSTORE_BASE64" | Out-Null
    Require-EnvironmentValue "ANDROID_KEYSTORE_PASSWORD" | Out-Null
    Require-EnvironmentValue "ANDROID_KEY_ALIAS" | Out-Null
    Require-EnvironmentValue "ANDROID_KEY_PASSWORD" | Out-Null
}

$keytoolCommand = Get-Command keytool -ErrorAction SilentlyContinue
$keytoolPath = $keytoolCommand.Source
if (-not $keytoolPath -and $env:JAVA_HOME) {
    $candidate = Join-Path $env:JAVA_HOME "bin\keytool.exe"
    if (Test-Path -LiteralPath $candidate) {
        $keytoolPath = $candidate
    }
}
if (-not $keytoolPath) {
    throw "keytool was not found. Install a JDK or set JAVA_HOME."
}

$output = & $keytoolPath -list -keystore $resolvedKeystore -alias $Alias -storepass $storePassword 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "keytool could not validate the keystore, alias, or store password."
}

Write-Output "Android release signing preflight passed."
Write-Output ("keystore={0}" -f $resolvedKeystore)
Write-Output ("alias={0}" -f $Alias)
Write-Output ("keytool={0}" -f $keytoolPath)
Write-Output "Secret values were not printed. Gradle still performs the final key-password check during assembleRelease."
