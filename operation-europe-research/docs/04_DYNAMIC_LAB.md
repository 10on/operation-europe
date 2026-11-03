# 04. Динамический стенд и эксперименты

## Два режима — два инструмента

**DOSBox Automation**: API для ввода, видеокадров, памяти, регистров и записи действий. По официальной документации версии 0.85.1 `features.debugger = false`: полноценные debugger endpoints **не реализованы**. Не пытаться обращаться к выдуманному `/breakpoint` API.

**DOSBox-X с Debugger**: real-mode breakpoints, трассировка, дизассемблер, дампы. Для анализа кодовых переходов использовать его **отдельно**; нельзя предполагать совместимость save-state между двумя эмуляторами.

## Базовая настройка DOSBox Automation

`config/dosbox-automation.example.conf` — минимальный добавочный фрагмент. В рабочий конфиг его секцию вносить после генерации config соответствующей версии.

```ini
[webserver]
webserver_enabled = on
webserver_bind_address = 127.0.0.1
webserver_port = 8386
```

Полный токен обязательно подаётся через `DOSBOX_API_TOKEN` или разрешённый token file. Без заголовка `Authorization: Bearer <token>` API возвращает 401. Проверка в браузере: `http://127.0.0.1:8386/api.html`.

### Проверка capability

```powershell
$env:DOSBOX_API_TOKEN = 'PUT-A-LOCALLY-GENERATED-SECRET-HERE'
python scripts/dosbox_api.py info
python scripts/dosbox_api.py status
python scripts/dosbox_api.py screenshot artifacts/frame.png
```

Сначала статус и `features`, затем запись/пауза/память. Не запускать api-server с `webserver_allow_remote=on` ради доступа с Mac: использовать SSH tunnel.

### Встроенные эндпоинты 0.85.1

```text
GET  /api/v1/status
GET  /api/v1/dosbox/info
GET  /api/v1/video/frame?format=png
GET  /api/v1/video/frame/info
GET  /api/v1/video/text           # если текстовый режим, иначе empty
GET  /api/v1/memory/0x1000/256   # raw binary
GET  /api/v1/cpu/state
POST /api/v1/memory/search       # width/start/end/value
POST /api/v1/input/sequence      # timed key/mouse events
POST /api/v1/input/record/start
POST /api/v1/input/record/stop
```

`dosbox_api.py` реализует только безопасную тестовую часть (GET/frame, read memory, single key). Для массовых входов расширить после подтверждения GUI навигации, с явным stop condition. Документация: https://www.dosbox-automation.org/0.85.1/automation/rest-api/index.html

### Ввод клавиши

```bash
python scripts/dosbox_api.py key KBD_enter
```

Типовое тело `/input/sequence`:

```json
{"events":[{"type":"key","key":"KBD_enter","pressed":true,"t":0},{"type":"key","key":"KBD_enter","pressed":false,"t":80}]}
```

Движок replay зависит от настроек CPU/clock, клавиатуры и RNG. Фиксировать `cycles`, core, keyboard layout и настройки эмулятора; подтверждать экран после каждого смыслового перехода. Повторение тех же клавиш не доказывает воспроизводимость боевого рандома.

## Структура одного опыта

```text
artifacts/experiments/EXP-001/
  before.png
  after.png
  before.ocr.json
  after.ocr.json
  action-sequence.json
  config-fingerprint.txt
  memory-before.bin       # только локально
  memory-after.bin        # только локально
  report.json
```

## Первые эксперименты — от лёгкого к сложному

| ID | Цель | Контроль |
|---|---|---|
| EXP-001 | открытие карточки одной дивизии | screenshot + schema GUI + обратный выход |
| EXP-002 | найти показанную характеристику в RAM | две разные величины, исключить UI-buffer |
| EXP-003 | приказ перемещения на соседний hex/tile | координаты до/после + карта без субъективной оценки |
| EXP-004 | проверка изменения расхода топлива/действия | до/после одного хода, seed/conditions |
| EXP-005 | атака на соседа | контроль RNG/числа итераций, минимум 20 прогонов если вариативно |

Сначала передвигать/читать, а не исследовать полный AI. На каждом шаге автоматизация должна распознавать текущий экран, а не пытаться нажимать всегда одно и то же количество клавиш.

## Отладчик DOSBox-X

Документация: https://github.com/joncampbell123/dosbox-x/blob/master/README.debugger . В сборках с debugger активируется клавиатурным shortcut (часто Alt+Pause; проверить текущую сборку), есть `DEBUGBOX`, `BP <seg> <off>`, `BPINT`, `MEMDUMPBIN`, `LOG`, `RUN`. Команды могут различаться по compile-time опциям; первым делом `HELP` в активном debugger.

Подтверждённый алгоритм исследователя:

1. Создать такую же начальную ситуацию в DOSBox-X (самостоятельный запуск, не импорт слепого save-state Automation).
2. Перейти к началу нужной функции по breakpoint, найденному из Ghidra + runtime mapping.
3. Проверить значения регистров, стек, сегментные регистры, смежные данные.
4. Сохранить небольшой бинарный дамп и лог в `artifacts/experiments/<id>`, записать режим CPU и адрес.
5. Сверить с гипотезой Ghidra; при расхождении обновить адресное отображение.

### Важные ограничения

- API `GET memory` читает **физические** данные или заданный сегмент; расширенная память и DOS XMS требуют учитывать банковые/страничные механизмы.
- Если `video/text` сообщил `is_text_mode=false`, не продолжать пытаться читать текстовый буфер. Использовать PNG + ROI.
- API чтения памяти и кадра по отдельности не гарантирует единого снимка **между двумя запросами**: при необходимости поставить игру на паузу безопасным доступным способом или сверить frame/cpu timestamp.

## Повтор динамической трассы TASK-010 (hub #49)

```powershell
python -I scripts/oe_trace_recheck.py --runs 2 --experiment TRACE-49-20261103
```

Скрипт N раз запускает `dosboxx_probe_session.py --auto --autotype --new-console --experiment ID` (новый флаг `--experiment` меняет только каталог вывода), проверяет каждый прогон `verify_runtime_reads.py` (только проверка), строит нормализованную трассу (load_base, BP CS:IP, DS, DX, строка DS:DX, AX open/read, побайтовое сравнение и sha256 буфера для SCEDATA и MAPINF), считает `trace_hash` и сравнивает с оригиналом `TASK-010/run-20261030T010340Z`. Результат: `artifacts/experiments/<ID>/comparison.json` и `report.json`. Таймаут одного прогона 600 с (затем убивается только запущенный им DOSBox-X). Окно DOSBox-X сворачивать нельзя: при `--minimize` AUTOTYPE не доходил до игры (0 hits). Окно остаётся открытым, но без фокуса.

## Unicorn против трассы (TASK-007A, хаб #50)

Команда: `python -I scripts/oe_unicorn_task007a.py [--trace-run <run-dir>] [--out <json>]`.
Исполняет 60 инструкций функции из `artifacts/experiments/TASK-007A/one-function.json` в Unicorn (16-bit real mode) с входным состоянием из трассы (`hits.json` TRACE-49): CS=0F24, DS=SS=4F5B, SP=SP(0394)+10, AL=1. Сегменты CALLF релоцируются на load base 0x849, как это делает загрузчик DOS. Вызовы 1000:977E/009B/0043/0032 и ближний 1000:6E64 заменены заглушками с семантикой DOS open/seek/read/close. На каждой точке трассы сравниваются регистры; при mapinf исключены BX/CX/DX (их меняют close и 6E64, не моделируются). Проверяются смещения seek (17743, 0) и SHA буферов чтения. Выход 0 — совпало, 1 — любое расхождение. Тест: `tests/test_oe_unicorn_task007a.py` (включая мутации трассы и данных).


## Наблюдение записи в память (DOSBox-X, `scripts/dosboxx_watch.py`, #226)

```
python -I scripts/dosboxx_watch.py --slot 1 --hours 12 --watch 17BE 17BF --experiment MOVE-226-20261103
```

- Сейв в рабочей копии должен уже содержать нужные приказы. Приказ дивизии хранится в её записи: +0xC/+0xD — цель x/y, +0xE — тип приказа (0 = Move, 0xFF — нет).
- Игра стартует под отладчиком (DEBUGBOX MAIN), клавиши вводит AUTOTYPE: логотип, Load Game, слот, «ready», Pass, часы, подтверждение. Параметры `--wait 15 --pause 15` проверены.
- На каждый адрес DS ставится BPM. Остановка определяется по совпадению регистров при опросе (`--poll`) и по изменению наблюдаемого значения.
- В `hits.json` пишутся регистры, адрес Ghidra, 32 байта кода, стек (SS:SP, SS:BP) и часы игры. В `timeline.json` — моменты изменения даты и часа (DS:0x43..0x47): по ним видно, что сейв загрузился и время идёт.
- `--frames` сохраняет кадры рабочего стола каждые 10 с — для отладки тайминга клавиш.
- Окно DOSBox-X должно быть видимо и с отдельной консолью (CREATE_NEW_CONSOLE). Если вывод перенаправлен в файл, отладчик рвёт связь.
- Ограничения: AUTOTYPE не следит за экраном. Запуск иногда сбивается (игра выходит в DOS), тогда его нужно повторить. С тремя адресами BPM три запуска подряд не удались; с двумя работает.
