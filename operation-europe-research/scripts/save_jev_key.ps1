$ErrorActionPreference = 'Stop'
$secretDir = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'OperationEurope\secrets'
[void](New-Item -ItemType Directory -Force -Path $secretDir)
$secretPath = Join-Path $secretDir 'jev.dpapi'
if (Test-Path -LiteralPath $secretPath) {
    throw 'Key file already exists; no overwrite performed.'
}
$jevSecret = Read-Host 'Paste Jev API key and press Enter (input is hidden)' -AsSecureString
try {
    if ($jevSecret.Length -eq 0) { throw 'Empty key; nothing saved.' }
    $encrypted = ConvertFrom-SecureString -SecureString $jevSecret
    Set-Content -LiteralPath $secretPath -Value $encrypted -Encoding ASCII
    Write-Host 'Saved encrypted Jev key (Windows DPAPI).'
} finally {
    $jevSecret.Dispose()
    Remove-Variable encrypted -ErrorAction SilentlyContinue
}
