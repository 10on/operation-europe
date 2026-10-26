# Импорт ОДНОГО EXE из копии игры в Ghidra-проект (headless, без авто-анализа по умолчанию).
# Использование: oe-ghidra main.exe            - импорт без анализа
#                oe-ghidra main.exe -Analyze   - с анализом (делайте после ручной проверки в GUI)
#                oe-ghidra -Gui                - открыть Ghidra GUI
param([string]$Exe = "", [switch]$Analyze, [switch]$Gui)
$ErrorActionPreference = "Stop"
$OE = if ($env:OE_ROOT) { $env:OE_ROOT } else { (Resolve-Path "$PSScriptRoot\..").Path }
$g = $env:OE_GHIDRA; if (-not $g -or -not (Test-Path $g)) { throw "Ghidra не найдена (OE_GHIDRA)" }
if ($Gui) { Start-Process (Join-Path $g "ghidraRun.bat"); return }
if (-not $Exe) { throw "Укажите имя файла из private\game-dos-working, например main.exe" }
$file = Join-Path $OE "private\game-dos-working\$Exe"; if (-not (Test-Path $file)) { throw "Нет файла $file" }
$proj = Join-Path $OE "private\ghidra-projects"
$ghArgs = @("`"$proj`"", "OperationEurope", "-import", "`"$file`"", "-overwrite")
if (-not $Analyze) { $ghArgs += "-noanalysis" }
$out = Join-Path $env:TEMP "oe_ghidra.out"; $err = Join-Path $env:TEMP "oe_ghidra.err"
$p = Start-Process -FilePath (Join-Path $g "support\analyzeHeadless.bat") -ArgumentList $ghArgs -Wait -PassThru -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err
Get-Content $out, $err -Encoding UTF8 -ErrorAction SilentlyContinue | Select-String -Pattern "Using Loader|Using Language|REPORT:|ERROR" | ForEach-Object { $_.Line }
Write-Host "Ghidra exit code: $($p.ExitCode); полный лог: $out"
exit $p.ExitCode
