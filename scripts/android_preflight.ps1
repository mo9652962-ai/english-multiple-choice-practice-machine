[CmdletBinding()]
param(
    [string]$ToolchainRoot = $env:EPM_ANDROID_TOOLCHAIN
)

$errors = @()
$projectRoot = Split-Path -Parent $PSScriptRoot
$androidRoot = Join-Path $projectRoot 'frontend\android'

if (-not [string]::IsNullOrWhiteSpace($ToolchainRoot)) {
    $toolchainJavaHome = Join-Path $ToolchainRoot 'jdk'
    $toolchainSdkRoot = Join-Path $ToolchainRoot 'sdk'
    if (Test-Path -LiteralPath (Join-Path $toolchainJavaHome 'bin\java.exe')) {
        $env:JAVA_HOME = $toolchainJavaHome
        $env:Path = (Join-Path $toolchainJavaHome 'bin') + ';' + $env:Path
    }
    if (Test-Path -LiteralPath $toolchainSdkRoot) {
        $env:ANDROID_HOME = $toolchainSdkRoot
        $env:ANDROID_SDK_ROOT = $toolchainSdkRoot
        $toolPaths = @(
            (Join-Path $toolchainSdkRoot 'platform-tools'),
            (Join-Path $toolchainSdkRoot 'emulator'),
            (Join-Path $toolchainSdkRoot 'cmdline-tools\latest\bin')
        )
        $existingToolPaths = $toolPaths | Where-Object { Test-Path -LiteralPath $_ }
        $env:Path = ($existingToolPaths -join ';') + ';' + $env:Path
    }
}

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    $errors += 'Node.js not found; Capacitor 8 requires Node.js 22+.'
} else {
    $nodeOutput = (& node --version 2>&1 | Out-String).Trim()
    if ($nodeOutput -notmatch '^v(2[2-9]|[3-9][0-9])(\.|$)') {
        $errors += "Node.js must be 22+: $nodeOutput"
    }
}

$java = Get-Command java -ErrorAction SilentlyContinue
if (-not $java) {
    $errors += 'Java not found; install and configure JDK 21.'
} else {
    $versionOutput = (& java -version 2>&1 | Out-String)
    if ($versionOutput -notmatch 'version "21(\.|"|-)') {
        $errors += "Java must be JDK 21: $($versionOutput.Trim())"
    }
}

$sdkRoot = $env:ANDROID_HOME
if ([string]::IsNullOrWhiteSpace($sdkRoot)) {
    $sdkRoot = $env:ANDROID_SDK_ROOT
}
if ([string]::IsNullOrWhiteSpace($sdkRoot) -or -not (Test-Path -LiteralPath $sdkRoot)) {
    $errors += 'Android SDK not found; set ANDROID_HOME or ANDROID_SDK_ROOT.'
} else {
    $requiredSdkPaths = @(
        (Join-Path $sdkRoot 'platforms\android-36'),
        (Join-Path $sdkRoot 'build-tools\36.0.0'),
        (Join-Path $sdkRoot 'platform-tools\adb.exe')
    )
    foreach ($path in $requiredSdkPaths) {
        if (-not (Test-Path -LiteralPath $path)) {
            $errors += "Missing Android SDK component: $path"
        }
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $androidRoot 'gradlew.bat'))) {
    $errors += 'frontend/android/gradlew.bat not found; run npx cap add android in frontend first.'
}

if ($errors.Count -gt 0) {
    Write-Error (($errors | ForEach-Object { "- $_" }) -join [Environment]::NewLine)
    exit 1
}

Write-Output 'Android preflight passed: JDK 21, SDK 36, Gradle wrapper available.'
