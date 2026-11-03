# Создаёт новый токен DOSBox Automation API и сохраняет его в пользовательской
# переменной окружения DOSBOX_API_TOKEN (HKCU\Environment). Значение не печатается
# и не пишется в файлы проекта. Старый private\dosbox\api_token.txt не читается.
# Использование: .\scripts\set_dosbox_token.ps1 [-Force]
param([switch]$Force)
$ErrorActionPreference = 'Stop'

$existing = [Environment]::GetEnvironmentVariable('DOSBOX_API_TOKEN', 'User')
if ($existing -and $existing -match '^[0-9a-fA-F]{64}$' -and -not $Force) {
    $env:DOSBOX_API_TOKEN = $existing
    Write-Host 'DOSBOX_API_TOKEN уже задан для пользователя (64 hex); оставлен без изменений. -Force — сгенерировать новый.'
    return
}

$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$token = -join ($bytes | ForEach-Object { $_.ToString('x2') })

[Environment]::SetEnvironmentVariable('DOSBOX_API_TOKEN', $token, 'User')
$env:DOSBOX_API_TOKEN = $token

$check = [Environment]::GetEnvironmentVariable('DOSBOX_API_TOKEN', 'User')
if ($check -ne $token) { throw 'Не удалось сохранить DOSBOX_API_TOKEN' }
Write-Host 'DOSBOX_API_TOKEN сохранён для пользователя (64 hex). Новые терминалы и приложения увидят его после перезапуска.'
