# Запуск DOSBox-X (с отладчиком) на КОПИИ игры. Использование: oe-dosboxx [-Run koei]
# Отладчик: Alt+Pause (или Debug-меню); команды: BP, BPM, G, T, D, R. Это отдельная программа БЕЗ HTTP API.
param([string]$Run = "")
$ErrorActionPreference = "Stop"
$OE = if ($env:OE_ROOT) { $env:OE_ROOT } else { (Resolve-Path "$PSScriptRoot\..").Path }
$exe = $env:OE_DOSBOX_X; if (-not (Test-Path $exe)) { throw "dosbox-x.exe не найден" }
$priv = Join-Path $OE "private"
$tpl = Get-Content (Join-Path $OE "config\dosboxx.conf.template") -Raw -Encoding UTF8
[IO.File]::WriteAllText((Join-Path $priv "dosboxx.conf"), $tpl.Replace("@RUN@", $Run), (New-Object Text.UTF8Encoding $false))
Start-Process -FilePath $exe -ArgumentList @("-conf", "dosboxx.conf", "-fastlaunch", "-nopromptfolder") -WorkingDirectory $priv
Write-Host "DOSBox-X запущен (диск C = private\game-dos-working, D = private\dos-tools)."