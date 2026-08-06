param(
    [Parameter(Mandatory = $true)]
    [string]$Source,
    [Parameter(Mandatory = $true)]
    [string]$Destination
)

$wordApp = $null
$document = $null

try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordApp.AutomationSecurity = 3
    $document = $wordApp.Documents.Open($Source, $false, $true, $false)
    $document.SaveAs2($Destination, 12)
}
finally {
    if ($document) {
        $document.Close($false)
        [Runtime.InteropServices.Marshal]::ReleaseComObject($document) | Out-Null
    }
    if ($wordApp) {
        $wordApp.Quit()
        [Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
