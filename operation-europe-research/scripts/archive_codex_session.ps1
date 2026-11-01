# Copies the saved session journal and research artifacts; never deletes originals.
[CmdletBinding()]
param(
    [string]$SessionId = '01a18559-27ea-7de2-8253-bea2be20318f',
    [string]$Destination = [Environment]::GetFolderPath('Desktop'),
    [string]$CodexHome = (Join-Path $env:USERPROFILE '.codex')
)

$ErrorActionPreference = 'Stop'
$parsedId = [guid]::Empty
if (-not [guid]::TryParse($SessionId, [ref]$parsedId)) {
    throw 'SessionId must be a UUID.'
}
$research = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$project = Split-Path $research -Parent
$journals = @(
    foreach ($folder in @('sessions', 'archived_sessions')) {
        $searchRoot = Join-Path $CodexHome $folder
        if (Test-Path -LiteralPath $searchRoot) {
            Get-ChildItem -LiteralPath $searchRoot -Recurse -File -Filter "*$SessionId*.jsonl"
        }
    }
)
if ($journals.Count -eq 0) { throw "No saved journal found for $SessionId" }
if ([string]::IsNullOrWhiteSpace($Destination)) { throw 'Specify -Destination.' }
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$destinationRoot = (Resolve-Path -LiteralPath $Destination).Path
# Refuse destinations inside the folders being copied (recursive self-copy).
$folders = @('artifacts', 'knowledge', 'docs', 'scripts', 'tests', 'schemas', 'agents')
foreach ($folder in $folders) {
    $sourceRoot = [IO.Path]::GetFullPath((Join-Path $research $folder)).TrimEnd('\')
    if ($destinationRoot.Equals($sourceRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $destinationRoot.StartsWith($sourceRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Destination cannot be inside $sourceRoot"
    }
}
$name = 'codex-{0}-{1}' -f $SessionId, (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$stage = Join-Path $destinationRoot $name
$zip = "$stage.zip"
New-Item -ItemType Directory -Path $stage | Out-Null
$journalDestination = Join-Path $stage 'session'
New-Item -ItemType Directory -Path $journalDestination | Out-Null
foreach ($journal in $journals) {
    $target = Join-Path $journalDestination $journal.Name
    if (Test-Path -LiteralPath $target) { throw "Duplicate journal filename: $($journal.Name)" }
    Copy-Item -LiteralPath $journal.FullName -Destination $target
}
foreach ($folder in $folders) {
    $source = Join-Path $research $folder
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination $stage -Recurse
    }
}
foreach ($name in @('AGENTS.md', 'README.md')) {
    $source = Join-Path $project $name
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $stage }
}
$files = @(Get-ChildItem -LiteralPath $stage -Recurse -File -Force)
$manifest = @($files | ForEach-Object {
    [pscustomobject]@{
        path = $_.FullName.Substring($stage.Length + 1)
        bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
})
[pscustomobject]@{
    session_id = $SessionId
    captured_utc = [DateTime]::UtcNow.ToString('o')
    project = $project
    scope = 'Saved journal and shared research artifacts; not all artifacts belong exclusively to this session.'
    excluded = @('private', '.git', 'Codex credentials/settings', 'external attachments not stored in copied folders')
    limitations = 'Run after agent activity ends for a stable snapshot. Journal may contain truncated outputs. No general secret scan is performed.'
    files = $manifest
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $stage 'manifest.json') -Encoding UTF8

Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($stage, $zip)
$archive = [IO.Compression.ZipFile]::OpenRead($zip)
try {
    $entries = @($archive.Entries | Where-Object { $_.Name -ne '' })
    if ($entries.Count -ne ($files.Count + 1)) { throw 'ZIP file count mismatch.' }
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        foreach ($item in $manifest) {
            $entry = $archive.GetEntry($item.path.Replace('\', '/'))
            if ($null -eq $entry) { $entry = $archive.GetEntry($item.path) }
            if ($null -eq $entry) { throw "Missing ZIP entry: $($item.path)" }
            $stream = $entry.Open()
            try { $digest = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '') }
            finally { $stream.Dispose() }
            if ($digest -ne $item.sha256) { throw "ZIP hash mismatch: $($item.path)" }
        }
    } finally { $sha.Dispose() }
} finally { $archive.Dispose() }
Write-Output "Verified ZIP: $zip"
Write-Output "Uncompressed copy retained: $stage"
Write-Output "ZIP SHA256: $((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash)"
