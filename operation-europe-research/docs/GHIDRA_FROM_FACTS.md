# Ghidra-проект из facts (#48)

Проект Ghidra для `main.exe` строится из `facts/main_exe.facts.json` (формат — `FACTS_FORMAT.md`), а не вручную.

## Команда

```
python -I scripts/oe_ghidra_from_facts.py [--project-dir private/ghidra-facts] [--force]
```

Вход: рабочая копия `private/game-dos-working/main.exe` (только чтение). Проект — `private/ghidra-facts/OeFacts` (в `.gitignore`, отдельный от проекта MCP: нет конфликта блокировок). `--force` удаляет существующий каталог проекта, но только внутри `private/`. Без `--force` непустой каталог — ошибка (код 3). Нужны Ghidra 12.2 (`OE_GHIDRA` или `C:\Tools\ghidra_*`) и JDK 25 (`JAVA_HOME` или `C:\Program Files\Eclipse Adoptium\jdk-25*`), пакет `jsonschema`. Время ~12 с.

## Что делает

1. Проверяет facts по `schemas/facts.schema.json`.
2. Сверяет SHA-256 `main.exe` с `binary.sha256` **до любого вызова Ghidra**; при расхождении — код 2, Ghidra не запускается.
3. `analyzeHeadless -import ... -noanalysis` (загрузчик MZ, база сегмента 0x1000) и post-script `scripts/ghidra/ApplyOeFacts.java`. Авто-анализ отключён: проект зависит только от facts и детерминирован.
4. Для каждой функции: дизассемблирование строго в диапазоне `start..end` (включительно), создание/переименование функции, тело = диапазон, plate-комментарий `[status] id: role | источники`.
5. Для `data_labels`: метка (`name` с недопустимыми символами заменяется на `_`, исходное имя — в EOL-комментарии вместе со статусом и источниками; статусы `inferred`/`observed` отражены в комментарии, не скрыты).
6. Пишет `artifacts/experiments/GHIDRA-FACTS-20261103/check.json` (id, имя, entry, min/max тела, число инструкций, размер, SHA-256 списка `адрес:длина:мнемоника`; без временных меток, поэтому повторный запуск даёт тот же файл).
7. Сверяет TASK-007A с `artifacts/experiments/TASK-007A/one-function.json`: адреса, длины (из `bytes_hex`) и мнемоники всех 60 инструкций, число и суммарный размер (158). Также сверяет `instruction_count`/`size_bytes` каждой функции с facts.

Коды выхода: 0 успех; 1 расхождение с facts/TASK-007A; 2 схема, SHA или адреса; 3 окружение/Ghidra или проект уже существует.

## Системы адресов

Для функций применяется только `kind=ghidra`; запись без такого адреса отвергается. `file_offset` не применяется, а лишь сверяется по формуле `file = 0x6000 + (seg-0x1000)*16 + off` (несоответствие = код 2).

Метки с `dgroup_offset`: сегмент DGROUP в `segments[]` задан как `load_base+0x4712`. Ghidra-образ с базой 0x1000 соответствует load base, поэтому DGROUP-сегмент Ghidra = 0x1000 + 0x4712 = **0x5712**, метка ставится на `5712:OFF` (например `SCEDATA` -> `5712:2E8C`). Это не runtime-адрес (в DOSBox-X DS=0x4F5B при load base 0x849). Для SCEDATA получившийся адрес независимо подтверждён записанным в facts `file_offset 0x4FFAC`; при расхождении скрипт останавливается. Для остальных меток такой сверки нет (`MAPINF.DAT` — статус `inferred`, пометка в комментарии).

Тесты: `python -I -m unittest discover -s tests -t . -p "test_oe_ghidra_from_facts.py"`.
