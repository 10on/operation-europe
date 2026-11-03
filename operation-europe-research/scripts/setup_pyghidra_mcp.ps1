# Ставит pyghidra-mcp в venv по ASCII-пути (JPype не принимает кириллицу в пути venv, см. MCP-001/MCP-002)
# и готовит отдельную копию main.exe для MCP-проектов Ghidra.
# Использование: .\scripts\setup_pyghidra_mcp.ps1 [-Venv C:\oe-tools\venv] [-Recreate]
param([string]$Venv = 'C:\oe-tools\venv', [switch]$Recreate)
$ErrorActionPreference = 'Stop'
$Ghidra = 'C:\Tools\ghidra_12.2_PUBLIC'
$Dist = "$Ghidra\Ghidra\Features\PyGhidra\pypkg\dist"
$OE = Split-Path -Parent $PSScriptRoot
$MainSha = '0b33be2fd37b965e5b92d1881f34226c1608eff6d0358787a7cb5049f218e9df'

if ($Venv -match '[^\x00-\x7F]') { throw "Путь venv должен быть ASCII: $Venv" }
if ($Recreate -and (Test-Path $Venv)) { Remove-Item -Recurse -Force $Venv }
if (-not (Test-Path "$Venv\Scripts\python.exe")) {
    New-Item -ItemType Directory -Force (Split-Path -Parent $Venv) | Out-Null
    python -m venv $Venv
}
$py = "$Venv\Scripts\python.exe"
& $py -m pip install -q --upgrade pip
& $py -m pip install -q "$Dist\pyghidra-3.2.0-py3-none-any.whl" "$Dist\jpype1-1.5.2-cp312-cp312-win_amd64.whl"
& $py -m pip install -q "pyghidra-mcp==0.3.0"
New-Item -ItemType Directory -Force "$(Split-Path -Parent $Venv)\tmp" | Out-Null

$dir = "$OE\private\mcp-002"
$copy = "$dir\main.exe"
if (-not (Test-Path $copy)) {
    New-Item -ItemType Directory -Force $dir | Out-Null
    Copy-Item "$OE\private\game-dos-working\main.exe" $copy
}
$sha = (Get-FileHash -Algorithm SHA256 $copy).Hash.ToLower()
if ($sha -ne $MainSha) { throw "SHA-256 копии main.exe не совпал: $sha" }

$env:GHIDRA_INSTALL_DIR = $Ghidra
# -I: иначе каталог scripts\ghidra из текущей папки перекрывает Java-пакет ghidra
& $py -I -c "import pyghidra; pyghidra.start(); from ghidra.framework import Application; print('pyghidra ok, Ghidra', Application.getApplicationVersion())"
Write-Host "Готово: $Venv; запуск сервера — scripts\pyghidra_mcp.cmd <claude|codex>"
