# Формат фактов oe-facts (v1)

## Назначение

`oe-facts` — версионированный JSON с метаданными о DOS-бинарнике (сейчас `main.exe`): адреса, имена функций и меток данных, сегменты, точки вызовов, статус и пути к источникам. Ghidra-скрипт (#48) позже будет читать этот файл и строить проект для `main.exe`.

Файлы:
- схема: `schemas/facts.schema.json` (JSON Schema draft 2020-12);
- первый набор фактов: `facts/main_exe.facts.json`;
- тесты: `tests/test_facts_schema.py` (`python -I -m unittest tests.test_facts_schema` из корня `operation-europe-research`).

## Правило: только метаданные

Файл не содержит исходных байтов бинарника, дизассемблера и поля `bytes`, `hex_bytes`, `disasm`, `instructions` (схема запрещает неизвестные поля на любом уровне). Факт записывается ссылкой на артефакт-источник, а не копией кода.

## Системы адресов

Каждый адрес — объект `{"kind": ..., "value": ...}`. Системы нельзя смешивать: значение записывается в той системе, в которой его измерили.

| kind | value | Смысл |
|---|---|---|
| `file_offset` | `0x...` | байтовое смещение в исходном EXE, с нуля |
| `ghidra` | `SSSS:OOOO` (hex) | адрес Ghidra; не runtime-адрес |
| `runtime` | `SSSS:OOOO` (hex) | сегмент:смещение в работающей DOSBox-X |
| `dgroup_offset` | `0x...` | смещение внутри DGROUP (DS-относительное) |

Связь file ↔ Ghidra для `main.exe` (проверено по TASK-007B и TASK-007A): `file = header_bytes + (seg - ghidra_image_base_segment) * 16 + off`, где `header_bytes = 0x6000`, `ghidra_image_base_segment = 0x1000`. Например, `1000:0043` ↔ file `0x6043`, `16db:0394` ↔ file `0xD144`.

Один и тот же объект может иметь несколько адресов (`start`, `at` — массивы), например одну точку и в file_offset, и в ghidra. Проверку соответствия делает тот, кто добавляет запись.

## Статусы

- `confirmed` — проверено измерением или дизассемблером, повторно воспроизводимо, источник это подтверждает;
- `observed` — наблюдено в одном прогоне или одном инструменте, без независимой проверки;
- `inferred` — вывод из косвенных данных; источник сам говорит «inferred»;
- `unknown` — источник не найден или не даёт ответа. Указывать с примечанием в `sources[].note`.

Статус берётся из источника, а не назначается по желанию. Если источник сам помечен `NEEDS_REVIEW`, это отражается в примечании.

## Поля

- `binary`: имя, SHA-256 (нижний регистр, 64 символа), `mz.header_bytes` (24576 для main.exe), `mz.ghidra_image_base_segment`, необязательный `runtime_example` (наблюдённый пример одного запуска, не факт для других запусков).
- `segments`: `name`, `kind` (`dgroup`|`code`), `relation` (например `load_base+0x4712`), `status`, `sources`.
- `functions`: `id`, `name`, `start` (≥1 адрес), `end` (необязательно, включающий конец диапазона), `instruction_count`, `size_bytes`, `role`, `status`, `sources`.
- `data_labels`: `id`, `name`, `at`, `type` (`string`|`buffer`|`word`|`unknown`), `length`, `status`, `sources`.
- `call_sites`: `id`, `description`, `at`, `target_function_id` (необязательно), `status`, `sources`.
- `sources[]`: `path` — путь от корня репозитория с прямыми слэшами (например `artifacts/experiments/TASK-007A/report.json`), `note` — необязательное примечание.

## Как это будет использовать #48

Ghidra-скрипт проверит схему и SHA-256 `main.exe`, затем создаст сегменты, функции, метки и ссылки из полей `start`/`at` в системе `ghidra`. Адреса `runtime` и `dgroup_offset` используются только для сверки, а не как адреса Ghidra. Записи со статусом `unknown` и `inferred` импортируются с пометкой, а не как подтверждённые.
