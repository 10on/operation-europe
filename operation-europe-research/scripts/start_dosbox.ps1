# Запуск DOSBox Automation с API на 127.0.0.1:8386. Монтирует КОПИЮ игры (private\game-dos-working), оригинал не трогает.
# Использование: oe-dosbox            - окно DOSBox, диск C: смонтирован, игра НЕ запускается
#                oe-dosbox -Run main.exe - дополнительно выполнить команду DOS`n#                oe-dosbox -Show         - показать обычное окно (по умолчанию окно сворачивается и не забирает фокус)
# Политика DOSBox Automation: монтировать можно только внутри каталога конфига; кириллица в абсолютном пути
# ломает конфиг, поэтому конфиг лежит в private\ и монтируется относительный путь game-dos-working.
param([string]$Run = "", [switch]$Show)
$ErrorActionPreference = "Stop"
$OE = if ($env:OE_ROOT) { $env:OE_ROOT } else { (Resolve-Path "$PSScriptRoot\..").Path }
if (-not $env:DOSBOX_API_TOKEN -or $env:DOSBOX_API_TOKEN -notmatch '^[0-9a-fA-F]{64}$') { throw "Нет DOSBOX_API_TOKEN: выполните . .\scripts\env.ps1" }
$exe = $env:OE_DOSBOX_AUTOMATION; if (-not (Test-Path $exe)) { throw "dosbox.exe (Automation) не найден" }
$priv = Join-Path $OE "private"
if (-not (Test-Path (Join-Path $priv "game-dos-working"))) { throw "Нет private\game-dos-working" }
$conf = Join-Path $priv "oe.conf"
$tpl = Get-Content (Join-Path $OE "config\oe.conf.template") -Raw
$tpl = $tpl.Replace("@GAME_DIR@", "game-dos-working").Replace("@RUN@", $Run)
[IO.File]::WriteAllText($conf, $tpl, (New-Object Text.UTF8Encoding $false))
$style = if ($Show) { "Normal" } else { "Minimized" }   # по умолчанию в фоне: окно не отбирает фокус и ввод у пользователя
Start-Process -FilePath $exe -ArgumentList @("-conf", "oe.conf") -WorkingDirectory $priv -WindowStyle $style
Write-Host "DOSBox запущен. API: $env:DOSBOX_API_URL (токен в env). Проверка: oe-api status"
