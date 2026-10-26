# 07. Данные, доказательства и тестирование будущего порта

## Canonical data model

Разделить **известные игровые данные** и **интерпретацию кода**. Не переносить UI напрямую в движок. Первая модель — эскиз, поля не подтверждены:

```ts
interface Scenario { id: string; turns?: number; initialUnits: Unit[]; }
interface Unit { id: string; side: string; position: Coord; equipmentId?: string; stats: Record<string, number>; }
interface Coord { x: number; y: number; }
interface Action { unitId: string; kind: string; target?: Coord; }
interface EngineResult { state: GameState; events: GameEvent[]; }
```

Сразу предусмотреть: принадлежность к сценарию, командир, маршрут, патроны/горючее/снабжение, возможности хода, видимость, состояния RNG, политические/стратегические события, журнал действий. Точные имена полей и схемы получим после анализа; текущие имена — placeholders, не факты об игре.

## Извлечение таблиц

Каждая extracted table хранит:

```text
source_sha256
source_kind = [DOS_EXE | DOS_DATA | DOS_SAVE | GENESIS_ROM | REFERENCE]
file_offset | runtime_address | ghidra_address
record_count, record_stride, byte_order, field_types
extraction_tool_revision
confidence + evidence_refs
```

Различать physical values, UI-scaled values, боевое внутреннее представление, отображение после rounding. Позднее можно сделать `parse(data)` и `serialize()` с round-trip тестом байтов **на незащищённых собственных тестовых примерах**.

## Differential / golden tests

1. Фиксировать исходный сценарий, версию DOS, шаги setup, unit ID, эмуль настройки.
2. Заранее знать, **что именно можно сравнить**: позицию юнита, стоимость хода, текст отказа, число оставшихся действий. Не пытаться сразу сравнить полный экран пиксель-в-пиксель между разными движками.
3. Для deterministic outcomes сравнивать точные числовые значения и side effects, включая rounding.
4. Для stochastic outcomes сначала исследовать seed/PRNG; пока RNG неизвестен, сравнивать распределения на серии опытов с согласованными условиями и честно фиксировать размер выборки.
5. Каждую найденную механику оформить как `fixture`: `initial_state -> action -> expected_result` и source evidence.
6. Добавлять regression test при каждом исправлении формулы.

## Качество определения источников

`confirmed` у таблицы — не просто наличие красивых чисел в диапазоне 0..100. Нужно минимум: известная привязка к двум видимым сущностям и xref из логики или независимая проверка в RAM; иначе `inferred`.

## Приоритет восстановлений

1. Параметры и идентификаторы подразделений.
2. Начальные сценарии, карты/типы местности.
3. Условия разрешённого приказа и movement cost.
4. Изменения состояния во времени (turn advancement).
5. Supply, repair, reinforcement.
6. Combat и RNG.
7. AI и победные условия.

## Разделение алгоритма и таблиц

Таблицы не обязаны быть кучей структур в EXE: их может быть мало, формулы могут быть закодированы в переходах и integer-математике, а графика и тексты могут находиться в тех же файлах. Не следует насильно превращать код в CSV, если движок вычисляет значения в циклах.
