# 06. Протокол взаимодействия агентов

## Разделение компетенций

- **Windows Agent:** скрипты, файловый inventory, Ghidra, построение списка структур, запуск экспериментального DOSBox, выгрузка воспроизводимых фактов. Инструкция — `agents/WINDOWS_AGENT.md`.
- **Mac Agent:** OCR, дешёвая модель Qwen-VL, screen-state classifier, проверка противоречий и компоновка кратких отчётов. `agents/MAC_AGENT.md`.
- **Cloud reviewer:** решает, какие гипотезы проверять следующими, читает отчёты/диффы/небольшие snippet, не копирует себе массивы изображений. `agents/CLOUD_REVIEWER.md`.

## Формат задач

Каждое задание — `schema_version`, `task_id`, `kind`, `owner`, `goal`, `inputs`, `expected_outputs`, `max_actions`, `stop_conditions`, `evidence_required`. Схема: `schemas/job.schema.json`. Сроки задач **не являются** SLA, агент просто исполняет ограниченное количество действий за один прогон.

Ограничения по умолчанию:
- **не больше 30 GUI actions** на один непроверенный navigation run;
- **не больше 5 самостоятельных попыток** восстановить неизвестный экран;
- **не более 2 повторений** одного удавшегося эксперимента без нового проверяемого вопроса;
- RAM scan — только в разумной области, с верхним лимитом размера и записью диапазона;
- Windows не должен автоматически стирать/патчить оригинальные файлы.

Это стартовые защитные пределы, меняются по явно записанному заданию.

## Контроль задач в начальной версии

Пока не нужен Redis, RabbitMQ и полноценный MCP. Рекомендуем структура:

```text
tasks/pending/TASK-001.json
runs/TASK-001/report.json
runs/TASK-001/observations/*.json
runs/TASK-001/images/*.png
```

Контроль назначения через Git issue / ручное `CLAIMED` в markdown task board; между двумя машинами для обмена использовать SCP/SMB. **Не** имитировать надёжную распределённую очередь простым watcher, который может дважды запустить игру. Эмулятор использует эксклюзивную блокировку задачи `emulator` одним агентом/процессом.

## Формат отчёта

`schemas/report.schema.json` задаёт обязательные поля. У каждого утверждения должен быть артефакт. Отчёт может содержать отдельный **human_summary_ru** до 1200 символов и список нерешённых вопросов.

Допустимое доказательство:

- локальный путь `artifacts/experiments/...`;
- SHA-256 исходного файла;
- `file offset`, адрес Ghidra, runtime `segment:offset` с указанием режима;
- пара before/after PNG, crop ROI и OCR результат;
- скрипт, который производит результат повторно;
- фрагмент ассемблера умеренной длины.

Недопустимо: «похоже, потери считаются по коэффициенту 0.7», если нет фиксированного эксперимента или найденного кода.

## Порядок проверок

1. Windows agent сдаёт inventory/report -> Cloud reviewer проверяет состав файлов/loader, назначает бинарный поиск.
2. Windows сдаёт table candidates -> Mac может прочесть GUI field и проверить candidate значения на конкретном screenshot.
3. Windows + Mac объединяют evidence -> Cloud reviewer принимает/отвергает гипотезу.
4. Для подтверждённых структур добавить regression tests и описание на уровне схемы.

## Короткий запрос к облаку

```text
Context: Operation Europe DOS, binary SHA256=..., task TASK-013.
Claim: field at DS:0x1234 might be unit fuel, confidence=inferred.
Evidence: EXP-042 before=81 after=77; EXP-043 before=50 after=46;
code xref FUN_..., files listed locally.
Alternatives: display cache vs game state; 16-bit scaled field.
Question: propose a single discriminating experiment.
```

Пример чисел/адресов вымышленный. Цель — получить план следующего опыта, а не печатать весь C-псевдокод в облачную сессию.
