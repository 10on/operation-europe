param([Parameter(Mandatory=$true)][string]$Batch)
$ErrorActionPreference = 'Stop'
$secretPath = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'OperationEurope\secrets\jev.dpapi'
$savedKey = $env:TYPESAFE_API_KEY
$secret = $null
try {
    if (-not $env:TYPESAFE_API_KEY) {
        $secret = ConvertTo-SecureString ((Get-Content -LiteralPath $secretPath -Raw).Trim())
        $env:TYPESAFE_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
    }
    & python (Join-Path $PSScriptRoot 'jev_probe.py') $Batch
    if ($LASTEXITCODE -ne 0) { throw 'Jev probe failed; inspect its sanitized run log.' }
} finally {
    $env:TYPESAFE_API_KEY = $savedKey
    if ($null -ne $secret) { $secret.Dispose() }
}
