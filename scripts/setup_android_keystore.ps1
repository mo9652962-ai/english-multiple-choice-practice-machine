[CmdletBinding()]
param(
    # Keystore output path: defaults outside the repo (%USERPROFILE%) to avoid accidental commits.
    [string]$KeystorePath = (Join-Path $env:USERPROFILE "epm-release-keystore\epm-release.keystore"),
    [string]$Alias = "epm-release",
    # Android requires key validity beyond 2033; 11000 days ~ 30 years.
    [int]$ValidityDays = 11000,
    [string]$DName = "CN=MoTi English Practice, OU=MoTi, O=MoTi, C=CN",
    # Skip generation (keystore already exists) and only configure GitHub secrets.
    [switch]$ConfigureSecretsOnly,
    [switch]$SkipPreflight
)

# EPM Android release keystore generator + GitHub secrets configurator.
# Passwords are entered interactively (never echoed), never written to the repo,
# never printed to output, and never persisted to plaintext temp files.
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

function ConvertFrom-SecurePlain([securestring]$SecureValue) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function Find-Keytool {
    $cmd = Get-Command keytool -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($candidate in @($env:JAVA_HOME, (Join-Path $env:USERPROFILE "jdk21"))) {
        if ($candidate) {
            $keytool = Join-Path $candidate "bin\keytool.exe"
            if (Test-Path -LiteralPath $keytool) { return $keytool }
        }
    }
    throw "keytool was not found. Install a JDK 21 or set JAVA_HOME."
}

function New-InteractivePassword([string]$Prompt) {
    while ($true) {
        Write-Host ""
        Write-Host $Prompt
        $first = Read-Host "Enter password (input hidden)" -AsSecureString
        $second = Read-Host "Confirm password" -AsSecureString
        $plainFirst = ConvertFrom-SecurePlain $first
        $plainSecond = ConvertFrom-SecurePlain $second
        if ($plainFirst -cne $plainSecond) {
            Write-Warning "The two entries do not match. Try again."
            continue
        }
        if ($plainFirst.Length -lt 8) {
            Write-Warning "Password must be at least 8 characters (16+ ASCII characters recommended)."
            continue
        }
        return $plainFirst
    }
}

$keytool = Find-Keytool
Write-Host "keytool: $keytool"
Write-Host "repo root: $repoRoot"

if (-not $ConfigureSecretsOnly) {
    if (Test-Path -LiteralPath $KeystorePath) {
        throw "Keystore already exists: $KeystorePath`nTo avoid destroying a signing identity, this script refuses to overwrite. See docs/android-release-signing.md for the rotation procedure."
    }
    $keystoreDir = Split-Path -Parent $KeystorePath
    if (-not (Test-Path -LiteralPath $keystoreDir)) {
        New-Item -ItemType Directory -Path $keystoreDir -Force | Out-Null
    }

    $storePassword = New-InteractivePassword "Set the keystore store password (16+ ASCII characters recommended)"
    $keyPassword = $storePassword  # Single-key keystore: key password equals store password (Gradle config still requires both).

    Write-Host ""
    Write-Host ("Generating keystore: {0}" -f $KeystorePath)
    Write-Host ("alias={0}  RSA 4096  validity={1} days" -f $Alias, $ValidityDays)
    & $keytool -genkeypair -v `
        -keystore $KeystorePath `
        -alias $Alias `
        -keyalg RSA -keysize 4096 `
        -validity $ValidityDays `
        -storepass $storePassword -keypass $keyPassword `
        -dname $DName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "keytool -genkeypair failed (exit=$LASTEXITCODE)." }

    # Show the SHA-256 fingerprint for offline records (no key material involved).
    $listOutput = & $keytool -list -v -keystore $KeystorePath -alias $Alias -storepass $storePassword 2>&1
    $sha256 = ($listOutput | Select-String "SHA256:").Line
    if ($sha256) {
        Write-Host ""
        Write-Host "Certificate SHA-256 fingerprint (record offline; do not commit to the repo):"
        Write-Host $sha256
    }
}
else {
    $storePassword = New-InteractivePassword "Enter the existing keystore store password"
    $keyPassword = New-InteractivePassword "Enter the existing keystore key password (enter the same value if it equals the store password)"
}

# ---- Preflight: reuse check_android_release_signing.ps1 (passwords passed via env vars, cleared afterwards). ----
if (-not $SkipPreflight) {
    Write-Host ""
    Write-Host "Running signing preflight (check_android_release_signing.ps1)..."
    $env:EPM_ANDROID_KEYSTORE_PASSWORD = $storePassword
    $env:EPM_ANDROID_KEY_ALIAS = $Alias
    $env:EPM_ANDROID_KEY_PASSWORD = $keyPassword
    try {
        & (Join-Path $PSScriptRoot "check_android_release_signing.ps1") -KeystorePath $KeystorePath -Alias $Alias
        if ($LASTEXITCODE -ne 0) { throw "Signing preflight failed (exit=$LASTEXITCODE)." }
    }
    finally {
        Remove-Item Env:EPM_ANDROID_KEYSTORE_PASSWORD -ErrorAction SilentlyContinue
        Remove-Item Env:EPM_ANDROID_KEY_ALIAS -ErrorAction SilentlyContinue
        Remove-Item Env:EPM_ANDROID_KEY_PASSWORD -ErrorAction SilentlyContinue
    }
}

# ---- GitHub secrets configuration (4 entries, consumed by the tag branch of .github/workflows/android.yml). ----
Write-Host ""
$configure = $ConfigureSecretsOnly
if (-not $configure) {
    $answer = Read-Host "Configure GitHub secrets now (requires gh CLI login)? [y/N]"
    $configure = ($answer -match '^[Yy]')
}
if ($configure) {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if (-not $gh) { throw "gh CLI not found. Install GitHub CLI and run 'gh auth login', then re-run (or configure manually per docs/android-release-signing.md)." }

    $b64File = Join-Path ([IO.Path]::GetTempPath()) ("epm-keystore-b64-" + [guid]::NewGuid().ToString("N") + ".txt")
    try {
        [IO.File]::WriteAllText($b64File, [Convert]::ToBase64String([IO.File]::ReadAllBytes($KeystorePath)))
        & gh secret set ANDROID_KEYSTORE_BASE64 --body-file $b64File
        if ($LASTEXITCODE -ne 0) { throw "Failed to set ANDROID_KEYSTORE_BASE64." }
        & gh secret set ANDROID_KEYSTORE_PASSWORD --body $storePassword
        if ($LASTEXITCODE -ne 0) { throw "Failed to set ANDROID_KEYSTORE_PASSWORD." }
        & gh secret set ANDROID_KEY_ALIAS --body $Alias
        if ($LASTEXITCODE -ne 0) { throw "Failed to set ANDROID_KEY_ALIAS." }
        & gh secret set ANDROID_KEY_PASSWORD --body $keyPassword
        if ($LASTEXITCODE -ne 0) { throw "Failed to set ANDROID_KEY_PASSWORD." }
        Write-Host "All 4 GitHub secrets configured."
    }
    finally {
        Remove-Item -LiteralPath $b64File -Force -ErrorAction SilentlyContinue
    }
}
else {
    Write-Host ""
    Write-Host "Skipping secrets configuration. Configure later (gh secret set NAME --body <value>):"
    Write-Host "  ANDROID_KEYSTORE_BASE64   <- base64 of the keystore file"
    Write-Host "  ANDROID_KEYSTORE_PASSWORD <- store password"
    Write-Host "  ANDROID_KEY_ALIAS         <- $Alias"
    Write-Host "  ANDROID_KEY_PASSWORD      <- key password"
}

Write-Host ""
Write-Host "=== Done ==="
Write-Host ("Keystore location (outside the repo; never commit): {0}" -f $KeystorePath)
Write-Host "For local release-build verification see docs/android-release-signing.md section 4."
