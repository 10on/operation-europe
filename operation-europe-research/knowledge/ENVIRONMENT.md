# ENVIRONMENT (Windows-стенд)
Дата: 2026-10-26. Статус: `oe-check` = ГОТОВО. Все версии наблюдены (observed) на этой машине.

## Быстрый старт для агента (3 команды)
```powershell
cd "<корень>\operation-europe-research"
. .\scripts\env.ps1          # PATH, JAVA_HOME, токен API, команды oe-*
oe-check                     # проверка окружения (ничего не меняет)
```
Управление DOS: см. DOS_INPUT.md (запуск игры — `koei`, мышь работает; `oe-ctl` — ввод/мышь/скриншот).
Команды: `oe-inv` (инвентаризация), `oe-dosbox [-Run main.exe]` (DOSBox + API), `oe-api status|info|screenshot <png>|memory|key`,
`oe-ghidra <exe> [-Analyze]` / `oe-ghidra -Gui`, `oe-validate <json>`.

## Версии и пути
| Компонент | Версия | Путь |
|---|---|---|
| Python | 3.12.10 + pyyaml 6.0.3 | %LOCALAPPDATA%\Programs\Python\Python312 |
| JDK | Temurin 25.0.4 (нужен Ghidra 12.2; 21 тоже стоит) | C:\Program Files\Eclipse Adoptium |
| Ghidra | 12.2 PUBLIC 20261016 | C:\Tools\ghidra_12.2_PUBLIC (данные: C:\ghidra-data) |
| DOSBox Automation | 0.85.1 (7567ec4), webserver 127.0.0.1:8386 | C:\Tools\dosbox-automation-0.85.1\... |
| DOSBox-X | 2026.10.01 | C:\DOSBox-X |
| Node 24 + pdfjs | для разбора PDF | private\tools |

## Важные особенности (получены опытом)
- Кириллица в профиле пользователя ломает Ghidra (OSGi/log4j) и конфиг DOSBox -> Ghidra и DOSBox Automation лежат в `C:\Tools`, данные Ghidra в `C:\ghidra-data` (прописаны в `support\launch.properties`).
- DOSBox Automation монтирует только внутри каталога конфига: конфиг генерируется в `private\oe.conf`, монтируется относительный `game-dos-working`.
- Ghidra 12.2 требует JDK 25 (JDK 21 -> "unsupported java version").
- Токен API лежит в `private\dosbox\api_token.txt` (в .gitignore, права только текущему пользователю), в сессию попадает через env.ps1. Не печатать и не коммитить.

## Данные
- `private/game-dos` — мастер-копия оригинала (43 файла), манифест SHA-256: `private/game-dos.sha256` (проверяется `oe-check`).
- `private/game-dos-working` — копия для эмулятора и Ghidra. Оригинал в корне проекта не изменялся.
- ROM Genesis SHA-256: 75a424e416a48cc2430e097c64dd95af1eb874b96ec9d9734aa2bb71a9b53b8a.
- `artifacts/inventory.json` — инвентаризация (7 исполняемых: end, fmdrv(.com), install, koei(.exe/.com), main, open).
- Ghidra-проект `private/ghidra-projects/OperationEurope`: main.exe и open.exe импортированы (loader: Old-style DOS Executable (MZ), язык x86:LE:16:Real Mode:default), анализ НЕ запускался.

## Проверено в ходе настройки
- DOSBox Automation: API status/info/screenshot работают (`artifacts/experiments/ENV-SMOKE/smoke.png`: диск C смонтирован, игра не запускалась). `debugger: false` в features этой сборки — для точек останова нужен DOSBox-X.
- inventory.py и tests/test_inventory.py: 3 теста OK.
