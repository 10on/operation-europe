# Operation Europe — исследование движка и воспроизводимый порт

Стартовый исследовательский репозиторий для **Operation Europe: Path to Victory 1939–45 (Koei)**. Приоритет — восстановление логики версии MS-DOS; Sega Genesis/Mega Drive остаётся **эталоном пользовательского опыта**, а не предполагаемо идентичным бинарным движком.

**Дата подготовки:** 2026-10-25. **Статус на 2026-10-26:** DOS-файлы получены и инвентаризированы (43 файла); первые MZ и файловые обращения исследованы. Текущие результаты и ограничения — в [knowledge/STATE.md](knowledge/STATE.md), [knowledge/DATA_FILES.md](knowledge/DATA_FILES.md) и [knowledge/FILE_IO.md](knowledge/FILE_IO.md). Подтверждённых адресов игровых таблиц пока нет.

## Цель

Получить проверяемое описание игровых данных, формул, последовательности ходов и AI, затем создать самостоятельный современный интерфейс (предпочтительно TypeScript / веб), с возможностью играть мышью и удобно сохраняться. Не начинать с копирования графики и не выдавать гипотезы за установленные правила.

## Машины

- **Windows — исследовательский стенд:** Intel Core i7-4790K, 32 ГБ DDR3, RTX A2000 **8 ГБ**. Оригинальные файлы, Ghidra, DOSBox Automation, DOSBox-X Debugger, эксперименты и сборка.
- **Mac — локальный наблюдатель:** Apple M1 Max, 64 ГБ unified memory. Qwen-VL через MLX, OCR-проверка, классификация кадров, структурированные отчёты. Видеокарту Windows не занимать Vision-моделью без необходимости.
- **Облачная модель — научный руководитель:** получает **короткие отчёты с доказательствами**, уточняет гипотезы и выдаёт следующие задачи. Не просматривать массово необработанные скриншоты и дампы в облаке.

## Начать отсюда

1. Прочитать [AGENTS.md](AGENTS.md), [docs/00_SCOPE.md](docs/00_SCOPE.md), [docs/01_ARCHITECTURE.md](docs/01_ARCHITECTURE.md).
2. На Windows установить Python 3.11+, Ghidra, DOSBox Automation и отдельно DOSBox-X с отладчиком; инструкции — [docs/08_WINDOWS_SETUP.md](docs/08_WINDOWS_SETUP.md).
3. Поместить законно полученные файлы DOS-игры **вне Git**, в `private/game-dos/`; выполнить `python scripts/inventory.py private/game-dos --out artifacts/inventory.json`.
4. Сохранить версию, SHA-256 и листинг. Не открывать бинарники в «режиме угадывания»: сперва изучить [docs/03_STATIC_ANALYSIS.md](docs/03_STATIC_ANALYSIS.md).
5. На Mac проверить Vision на тестовом скриншоте: [docs/09_MAC_SETUP.md](docs/09_MAC_SETUP.md).
6. Стартовая карточка проекта — `examples/TASK-001.json`, шаблон результата — `examples/REPORT-EXAMPLE.json`.

## Карта документации

| Файл | Назначение |
|---|---|
| `docs/00_SCOPE.md` | цели, границы, гипотезы, критерии успеха |
| `docs/01_ARCHITECTURE.md` | топология Windows/Mac/cloud, обмен, безопасность |
| `docs/02_SOURCES.md` | проверенные ссылки, неизвестное, исходные данные |
| `docs/03_STATIC_ANALYSIS.md` | инвентаризация, DOS MZ/COM/overlays, Ghidra, таблицы |
| `docs/04_DYNAMIC_LAB.md` | DOSBox Automation, скриншоты, память, DOSBox-X |
| `docs/05_VISION_OCR.md` | каскад OCR/OpenCV/Qwen, калибровка, контроль ошибок |
| `docs/06_AGENT_PROTOCOL.md` | задачи, очереди, доказательства, эскалация |
| `docs/07_DATA_TESTING.md` | модель данных, адреса, схемы, differential testing |
| `docs/08_WINDOWS_SETUP.md` | пошаговая настройка Windows |
| `docs/09_MAC_SETUP.md` | MLX/Qwen на M1 Max и обмен кадрами |
| `docs/10_LEGAL_RELEASE.md` | авторские права и безопасная публикация |
| `docs/11_ROADMAP.md` | этапы, чекпоинты и критерии готовности |
| `docs/12_FIRST_SESSION.md` | инструкция первого реального исследовательского сеанса |

Агенты получают инструкции из `agents/`; общие принципы — `AGENTS.md`.

## Рабочее дерево

```text
private/                  # локально, не в Git: оригинальная игра, ROM, токены
artifacts/                # генерируемые материалы и результаты, не коммитить огромные дампы
  inventory.json
  experiments/<id>/       # скрин, OCR, память, протокол, report.json
knowledge/                # коммитить только подтвержденные извлечения и отчеты
scripts/                  # проверяемые утилиты
schemas/                  # форматы задач/отчетов
```

`private/`, `knowledge/`, `artifacts/experiments/` создаются при работе; текущий архив не содержит игру и не содержит результат анализа. Токены не хранить в репозитории.

## Используемые утилиты (без дополнительных зависимостей Python)

```bash
python scripts/inventory.py private/game-dos --out artifacts/inventory.json
python scripts/dosbox_api.py status
python scripts/dosbox_api.py screenshot artifacts/frame.png
python scripts/dosbox_api.py key KBD_enter
python scripts/dosbox_api.py memory 0x0000 256 artifacts/low-memory.bin
python scripts/validate_json.py schemas/job.schema.json examples/TASK-001.json
```

Команды для DOSBox требуют уже запущенный DOSBox Automation, действующий `DOSBOX_API_TOKEN` и настроенный локальный сервер на `127.0.0.1:8386`. Скрипт инвентаризации **ничего не исполняет**, только читает файлы. Это стартовый инструментарий, не готовый автоматический декомпилятор.

## Правило приоритета

**Подтверждённый дизассемблированный код > подтверждённый дамп памяти > воспроизводимый эксперимент > документация/гайд > предположение модели.** При противоречии не усреднять: формулировать конкурирующие гипотезы и назначать проверку.
