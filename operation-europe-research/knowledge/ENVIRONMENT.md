# ENVIRONMENT (Windows-стенд)
Дата: 2026-10-26. Инструменты установлены; `oe-check` требует заранее заданную переменную `DOSBOX_API_TOKEN`. Версии наблюдены (observed) на этой машине.

## Быстрый старт для агента
```powershell
cd "<корень>\operation-europe-research"
.\scripts\set_dosbox_token.ps1   # 2026-11-03: генерирует новый токен в пользовательскую переменную DOSBOX_API_TOKEN (HKCU), значение не печатает; -Force — заменить
. .\scripts\env.ps1          # PATH, JAVA_HOME, команды oe-*; токен не загружает
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
- Токен API должен быть заранее задан в `DOSBOX_API_TOKEN`; `env.ps1` его не читает из файлов и не печатает. Старый файл с токеном пока существует (`private\dosbox\api_token.txt`); его безопасную миграцию координирует владелец стенда. Содержимое файла в отчёты не переносить.

## Данные
- `private/game-dos` — мастер-копия оригинала (43 файла), манифест SHA-256: `private/game-dos.sha256` (проверяется `oe-check`).
- `private/game-dos-working` — копия для эмулятора и Ghidra. Оригинал в корне проекта не изменялся.
- ROM Genesis SHA-256: 75a424e416a48cc2430e097c64dd95af1eb874b96ec9d9734aa2bb71a9b53b8a.
- `artifacts/inventory.json` — инвентаризация (7 исполняемых: end, fmdrv(.com), install, koei(.exe/.com), main, open).
- Ghidra-проект `private/ghidra-projects/OperationEurope`: main.exe и open.exe импортированы (loader: Old-style DOS Executable (MZ), язык x86:LE:16:Real Mode:default), анализ НЕ запускался.

## Проверено в ходе настройки
- DOSBox Automation: API status/info/screenshot работают (`artifacts/experiments/ENV-SMOKE/smoke.png`: диск C смонтирован, игра не запускалась). `debugger: false` в features этой сборки — для точек останова нужен DOSBox-X.
- inventory.py и tests/test_inventory.py: 3 теста OK.

## Повторная проверка TASK-004 (2026-10-26)
- До исправления загрузки токена из файла `scripts/check_env.py`, запущенный после `. .\scripts\env.ps1`, завершился кодом 0: Python 3.12.10, PyYAML 6.0.3, JDK 25.0.4.1, пути Ghidra/DOSBox, формат токена, манифест мастер-копии, рабочая копия и inventory прошли проверку. Значение токена не выводилось.
- Версии DOSBox-X 2026.10.01 и DOSBox Automation 0.85.1 подтверждены полями `FileVersion`/`ProductVersion` файлов EXE. Версия Ghidra 12.2 — строкой `application.version` в `Ghidra/application.properties`; `support/analyzeHeadless.bat` существует. Хеши и команды — в `artifacts/experiments/TASK-004/verification.txt`.
- На момент этой проверки процесс DOSBox не запущен; локальный API `127.0.0.1:8386` не отвечает (`WinError 10061`). Это не отменяет предыдущий ENV-SMOKE. Для нового динамического опыта сначала запустить эмулятор из рабочей копии и повторно проверить `status`/`info`.
- Ghidra GUI loader, entry point и пригодность DOSBox-X debugger в этой задаче повторно не проверялись. Перед headless-анализом и точками останова нужны отдельные проверки по `docs/03_STATIC_ANALYSIS.md` и `docs/04_DYNAMIC_LAB.md`.
- `check_env.py` исправлен на документированный `/api/v1/status`; `env.ps1` больше не читает токен из файла. В новой чистой сессии переменная токена отсутствует, поэтому `oe-check` ожидаемо завершился кодом 1 только из-за проверки `DOSBOX_API_TOKEN`. Для нового API-сеанса токен надо подать через переменную окружения; старый файл пока не удалён.
- План миграции существующего токена: владелец стенда перенесёт значение в пользовательскую переменную окружения Windows без вывода значения, проверит совпадение в новой сессии и только затем удалит старый файл. До его подтверждения миграция не считается выполненной.
- `start_dosbox.ps1` и `check_env.py` при пустой переменной теперь прямо объясняют, что нужен `DOSBOX_API_TOKEN`; `env.ps1` сохраняет уже заданную переменную. Проверено без запуска DOSBox, в отдельной PowerShell-сессии с временным синтетическим значением для теста сохранения.

## Ghidra MCP (pyghidra-mcp), 2026-11-03
- Установка: `.\scripts\setup_pyghidra_mcp.ps1` — venv `C:\oe-tools\venv` (только ASCII-путь: JPype не принимает кириллицу в пути venv, см. MCP-001/MCP-002), pyghidra 3.2.0 и jpype1 1.5.2 из дистрибутива Ghidra 12.2, `pyghidra-mcp==0.3.0`; копия main.exe `private/mcp-002/main.exe` со сверкой SHA.
- Запуск сервера: `scripts\pyghidra_mcp.cmd <claude|codex>`; у каждого клиента свой проект `private/mcp-002/project-<client>` (один проект Ghidra не открыть двумя процессами). Первый старт с анализом ~33 с, далее ~13 с. Имя программы в инструментах: `/main.exe-84a561`; адреса — в нумерации Ghidra (база 0x1000), не runtime.
- **Claude Code:** подключён (`claude mcp add --scope local ghidra -- cmd /c <путь>\pyghidra_mcp.cmd claude`, запись в `~/.claude.json`, не в git); `claude mcp get ghidra` → Connected. Регистрировать из PowerShell: Git Bash превращает `/c` в `C:/`.
- **Codex — не доделано.** В `~/.codex/config.toml` добавлен `[mcp_servers.ghidra]` (`command="cmd"`, `args=["/c", <путь>\pyghidra_mcp.cmd, "codex"]`, `startup_timeout_sec=120`, `tool_timeout_sec=300`); резервная копия `config.toml.bak-20261103`. Наблюдено в `codex exec`: (1) до добавления `PYTHONUTF8=1` в launcher Codex переставал читать stderr сервера («stream did not contain valid UTF-8») — исправлено; (2) сервер стартует ~13 с, короткий ход завершается раньше, чем инструменты появятся; (3) инструменты отложенные, модель находит их только через tool discovery; (4) после ожидания `ghidra/read_bytes` найден, но вызов отклонён: «MCP tool call requires approval, but approval policy is never». Осталось: в интерактивном Codex одобрить инструменты ghidra (или задать политику одобрения для этого сервера) и один раз проверить `read_bytes 1000:0043` = `558bec8b5e068b4e0a8b5608b43fcd2173005dcb`. Задача хаба #220.
