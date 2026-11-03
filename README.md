# Operation Europe: Path to Victory 1939–45 — реверс-инжиниринг

Проект по изучению движка стратегии Koei **Operation Europe: Path to Victory 1939–45** (DOS) с целью воспроизвести правила и написать современный порт (TypeScript/веб). Sega Genesis-версия — референс поведения, не гарантированно тот же движок.

## Структура репозитория

| Путь | Что это |
|---|---|
| `Operation_Europe_Path_To_Victory_1939_To_45/` | **Оригинал DOS-версии** (43 файла по инвентаризации 2026-10-26, только чтение) |
| `Operation Europe - Path to Victory 1939-45 (USA).gen` | ROM Sega Genesis, 1 МБ (SHA-256 `75a424e4…b53b8a`) |
| `operation-europe-research/` | Исследовательский стенд: документация, скрипты, схемы отчётов |
| `AGENTS.md` | Быстрый вход для AI-агентов (читать первым) |

Подробный план и протоколы — в `operation-europe-research/` (`README.md`, `AGENTS.md`, `docs/00…12`, `PIPELINE.md`).

План и статусы задач ведутся в Agent Hub (проект `operation-europe-dos-reverse`, эпики M1–M17). Актуальная сводка фактов — начало [`knowledge/STATE.md`](operation-europe-research/knowledge/STATE.md). Исходные файлы лежат в корне; мастер-копия и рабочая копия для эмулятора уже созданы в `operation-europe-research/private/`.

## Что известно о DOS-версии (первичный осмотр)

**Исполняемые** (MZ EXE): `main.exe` (366 КБ, основной движок), `open.exe` (интро), `end.exe` (концовки), `install.exe`, `koei.exe`; `koei.com`, `fmdrv.com` — маленькие COM (FM-драйвер звука).

**Данные** (гипотезы по именам/заголовкам, не подтверждены):
- `scedata` — первые 9 600 байт состоят из 12 текстовых участков по 800 байт с нулевым дополнением; далее есть смешанные данные. Назначение участков ещё проверяется.
- `msg`/`msg.16p` и `emsg`/`emsg.16p` — каждая пара побайтно идентична; формат и назначение пока неизвестны.
- `hexmap.dat`, `bigmap.dat`, `midmap.dat`, `mapinf.dat`, `mappno.dat`, `hexunit.dat`, `hexdisp.dat` — карта и гексы/юниты (`hexmap.dat` — байты типов местности, малые значения 05/09/0a).
- `event.dat`, `scesel.dat`, `sceend.dat` — события и выбор/финалы сценариев.
- `arms.sil` — силуэты оружия/техники (графика, 121 КБ).
- `face.dat`, `*grp.dat`, `*.npk`, `hexfont*.dat`, `koeilogo.fnt` — графика, портреты, шрифты (`.npk` — упакованная графика).
- `*.bat`, `install.sys`, `c_fig.sys`, `disk-*.ver` — установка/загрузка.

Консольная Ghidra подтвердила loader MZ и 16-битный real mode для `main.exe`/`open.exe`; это Microsoft C, упаковщиков нет. Файлы открываются через общий wrapper DOS `INT 21h/AH=3Dh`; `DS` = load segment + `0x4712` (подтверждено отладчиком DOSBox-X и relocations). Чтения `SCEDATA` и `MAPINF.DAT` сверены в рантайме побайтно, файловый ввод-вывод шести сценариев снят ([`FILE_MAP.md`](operation-europe-research/knowledge/FILE_MAP.md), [`FILE_IO.md`](operation-europe-research/knowledge/FILE_IO.md); строка рядом с `MSG` — на деле `MSGRP.DAT`). Не подтверждены полные форматы полей, адреса игровых таблиц и формулы боя.

## Быстрый старт

```bash
cd operation-europe-research
python scripts/inventory.py ../Operation_Europe_Path_To_Victory_1939_To_45 --out artifacts/inventory.json
python -m unittest tests/test_inventory.py
```

Запуск игры — только через DOSBox/DOSBox-X (см. `docs/04_DYNAMIC_LAB.md`, `docs/08_WINDOWS_SETUP.md`). Инструменты: Python 3.11+, Ghidra, DOSBox-X с отладчиком.

## Правовое

Оригинальные файлы и ROM не публиковать и не коммитить; в Git — только выводы, хеши, таблицы своими словами, малые фрагменты. См. `operation-europe-research/docs/10_LEGAL_RELEASE.md`.
