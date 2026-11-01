# Подключение окружения проекта: . .\scripts\env.ps1   (dot-sourcing, в КАЖДОЙ новой сессии)
# Ничего не устанавливает; только выставляет PATH/переменные и даёт короткие команды oe-*.
$script:OE = (Resolve-Path "$PSScriptRoot\..").Path
$script:Tools = "C:\Tools"   # ASCII-путь: кириллица в профиле ломает Ghidra/DOSBox

$py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312"
$jdk = Get-ChildItem "C:\Program Files\Eclipse Adoptium" -Directory -Filter "jdk-25*" -ErrorAction SilentlyContinue | Select-Object -First 1
$ghidra = Get-ChildItem $Tools -Directory -Filter "ghidra_*" -ErrorAction SilentlyContinue | Select-Object -First 1
$dba = Get-ChildItem $Tools -Recurse -Filter dosbox.exe -ErrorAction SilentlyContinue | Where-Object { $_.FullName -like "*dosbox-automation*" } | Select-Object -First 1

$env:OE_ROOT = $OE
$env:OE_PYTHON = Join-Path $py "python.exe"
if ($jdk) { $env:JAVA_HOME = $jdk.FullName }
$env:OE_GHIDRA = if ($ghidra) { $ghidra.FullName } else { "" }
$env:OE_DOSBOX_AUTOMATION = if ($dba) { $dba.FullName } else { "" }
$env:OE_DOSBOX_X = "C:\DOSBox-X\dosbox-x.exe"
$env:Path = "$py;$py\Scripts;$($env:JAVA_HOME)\bin;$env:Path"

# Токен DOSBox API задаётся только через уже существующую DOSBOX_API_TOKEN.
# Не читать секрет из файла и не печатать его в логи.
$env:DOSBOX_API_URL = "http://127.0.0.1:8386"

function oe-check   { & $env:OE_PYTHON "$OE\scripts\check_env.py" @args }
function oe-inv     { & $env:OE_PYTHON "$OE\scripts\inventory.py" "$OE\private\game-dos" --out "$OE\artifacts\inventory.json" }
function oe-dosbox  { & "$OE\scripts\start_dosbox.ps1" @args }
function oe-api     { & $env:OE_PYTHON "$OE\scripts\dosbox_api.py" @args }
function oe-iolog   { & $env:OE_PYTHON "$OE\scripts\oe_iolog.py" @args }
function oe-dosboxx { & "$OE\scripts\start_dosboxx.ps1" @args }
function oe-ctl     { & $env:OE_PYTHON "$OE\scripts\dosbox_ctl.py" @args }
function oe-boot { param([string]$To="menu",[string]$Input_="",[switch]$Show) if (-not $Input_) { $Input_ = if ($To -eq "newgame") { "keyboard" } else { "mouse" } } if (Get-Process dosbox -ErrorAction SilentlyContinue) { throw 'DOSBox process already running - aborting boot' }; & "$OE\scripts\start_dosbox.ps1" -Run "fmdrv`nmain" -Show:$Show | Out-Null; & $env:OE_PYTHON "$OE\scripts\boot_game.py" --to $To --input $Input_ }
function oe-record { param([ValidateSet("start","stop","note")]$cmd,$name,[Parameter(ValueFromRemainingArguments)]$rest) & $env:OE_PYTHON "$OE\scripts\record_session.py" $cmd $name @rest }
function oe-ghidra  { & "$OE\scripts\ghidra_import.ps1" @args }
function oe-validate{ param([ValidateSet("report","job")]$kind,$file) & $env:OE_PYTHON "$OE\scripts\validate_json.py" "$OE\schemas\$kind.schema.json" $file }
Write-Host "OE env ready: oe-check | oe-inv | oe-boot [menu|scenarios|newgame] | oe-record start|stop|note <имя> | oe-dosbox | oe-dosboxx | oe-ctl | oe-api status|info|screenshot | oe-ghidra <exe> | oe-validate report|job <file>"
