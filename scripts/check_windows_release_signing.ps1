[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Artifact,
    [switch]$RequirePublicCertificate,
    [switch]$RequireCiVariables
)

# Validate Authenticode signatures without printing certificate private data or
# any signing secret.  The public-release path rejects self-signed certificates.
$ErrorActionPreference = 'Stop'
$codeSigningOid = '1.3.6.1.5.5.7.3.3'

function Require-EnvironmentValue([string]$Name) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required Windows signing environment variable: $Name"
    }
}

if ($RequireCiVariables) {
    Require-EnvironmentValue 'WINDOWS_CSC_LINK'
    Require-EnvironmentValue 'WINDOWS_CSC_KEY_PASSWORD'
}

foreach ($rawPath in $Artifact) {
    $resolvedPath = (Resolve-Path -LiteralPath $rawPath -ErrorAction Stop).Path
    $signature = Get-AuthenticodeSignature -LiteralPath $resolvedPath
    if ($signature.Status -ne 'Valid') {
        throw "Unsigned or invalid Windows artifact: $resolvedPath (status=$($signature.Status))"
    }

    $certificate = $signature.SignerCertificate
    if ($null -eq $certificate) {
        throw "Windows artifact has no signer certificate: $resolvedPath"
    }
    if ($certificate.NotAfter -le (Get-Date)) {
        throw "Expired Windows signing certificate: $resolvedPath (NotAfter=$($certificate.NotAfter))"
    }

    $ekuOids = @($certificate.EnhancedKeyUsageList | ForEach-Object { $_.ObjectId.Value })
    if ($codeSigningOid -notin $ekuOids) {
        throw "Windows signer lacks Code Signing EKU: $resolvedPath"
    }
    if ($RequirePublicCertificate -and $certificate.Subject -eq $certificate.Issuer) {
        throw "Self-signed Windows certificate is not accepted for public release: $resolvedPath"
    }

    Write-Output ("Windows signing preflight passed: path={0}; status={1}; subject={2}; issuer={3}" -f `
        $resolvedPath, $signature.Status, $certificate.Subject, $certificate.Issuer)
}
