# Инструкции для агентов (корень проекта)

Проект: реверс DOS-игры **Operation Europe: Path to Victory 1939–45** (Koei). Язык общения/документации — русский.

## Читать по порядку
1. `README.md` (этот уровень) — карта и известные факты.
2. `operation-europe-research/AGENTS.md` — обязательные правила (доказательства, `report.json`, confidence, запреты).
3. `operation-europe-research/docs/00_SCOPE.md`, затем инструкция роли в `operation-europe-research/agents/`.

## Ключевые правила (сжато)
- Оригиналы (`Operation_Europe_Path_To_Victory_1939_To_45/`, `*.gen`) **не изменять и не коммитить**; работать с копиями в `operation-europe-research/private/` (в `.gitignore`).
- Не выдавать гипотезы за факты: нужны файл, SHA-256, смещение, метод проверки. Уровни: `confirmed` > `observed` > `inferred` > `unknown`.
- Не смешивать file offset / Ghidra address / `segment:offset` / линейный адрес.
- EXE исполнять только в DOSBox/DOSBox-X, не в Windows.
- Артефакты экспериментов — в `operation-europe-research/artifacts/experiments/<id>/` с `report.json` по `schemas/report.schema.json`.
- Облаку — краткие отчёты, не дампы и бинарники.
- Приоритет источников: дизассемблер > дамп памяти > эксперимент > гайды > догадка модели.

## Окружение
- Windows 10, PowerShell/Git Bash; Python 3.11+. Скрипты — `operation-europe-research/scripts/` (`inventory.py`, `dosbox_api.py`, `validate_json.py`), без внешних зависимостей.
- Токен DOSBox API — только в переменной `DOSBOX_API_TOKEN`, не в файлах.
- Каталога `private/game-dos/` ещё нет; игра лежит в корне — при работе по докам подставляйте этот путь или создайте копию.

## Следующие шаги
Инвентаризация (`inventory.py`) → разбор MZ-заголовков `main.exe`/`open.exe`/`end.exe` (проверить overlays) → форматы `scedata`, `hexmap.dat`, `msg` → загрузка `main.exe` в Ghidra (16-bit real mode) → динамическая сверка в DOSBox-X. См. `docs/03_STATIC_ANALYSIS.md`, `docs/12_FIRST_SESSION.md`.
