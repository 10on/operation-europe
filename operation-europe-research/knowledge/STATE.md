# STATE — точка продолжения (2026-10-26)

## Где мы
- Окружение готово (`oe-check` = ГОТОВО): Python 3.12, JDK 25, Ghidra 12.2 (C:\Tools), DOSBox Automation 0.85.1 (C:\Tools), DOSBox-X (C:\DOSBox-X), NASM. Подробно: `ENVIRONMENT.md`.
- Данные: `private/game-dos` (мастер-копия + `game-dos.sha256`), `private/game-dos-working` (копия для эмулятора/Ghidra). Оригиналы не менялись.
- Этап 1 (глоссарий) готов: `operation_europe_glossary_stage1/` (glossary, ui_screens, ui_transitions, scenarios, units_terrain, game_logic, platform_differences, unverified_questions, source_index). YAML валидны.
- Ghidra: main.exe и open.exe импортированы (MZ, x86 16-bit real mode), анализ не запускался.
- Игра в DOSBox: вход `oe-boot menu|scenarios|newgame` (клавиатурный проход ~65 с до стратегической карты France, Allies, Very Easy). Мышь работает (INT 33h), см. `DOS_INPUT.md`; путь экранов — `DOS_SCREENS.md`; запись ручного прохождения `artifacts/experiments/PLAY-001`.
- Окно DOSBox по умолчанию открывается свёрнутым (`-Show` — обычное).

## Текущее состояние игры (если DOSBox ещё запущен)
Стратегический экран France (5.10.40 00:00, Army Cmdr Bauxdey). В этой сессии нажатием Enter на стратегическом экране открылся запрос «How long should we wait, sir (1-24)?» (т.е. Pass); оно висит. Игровое сохранение НЕ делалось (DOSBox-сессия временная; для продолжения — `oe-boot newgame`).

## Наблюдения о памяти (observed, не проверено повторно)
Поиск слов на стратегическом экране (Infantry 12811, Tanks 217, Mech 390, Arty 411, Repair 425, Supply 762): 12811 — 39 совпадений кластером около 0x413DE..0x41549 (шаг 6/8 — кандидат: таблица батальонов/полков), прочие числа дают много совпадений. Физические адреса DOSBox, не сегмент:смещение. Нужен дифференциальный метод (изменить параметр → пересканировать).

## Следующие шаги
1. Пройти экраны Info (Units/Cities/Commanders/Armaments/Victory) клавиатурой, снять скриншоты (`artifacts/experiments/MAP-001`).
2. Найти в RAM таблицу полков/батальонов по числам с экрана Info-Units (дифференциально: Orgz/Supply/Move меняют значения).
3. Карта: Field Map (1:130000?) — найти массив местности (hexmap.dat/bigmap.dat/midmap.dat — форматы неизвестны).
4. Ghidra: entry point main.exe, xrefs на найденные адреса данных.
5. Genesis-мануал не получен (ссылка в source_index.yaml); расхождения консоли/DOS — в `unverified_questions.md`.

## Правила (не забывать)
Оригиналы не менять и не коммитить; гипотезы помечать (confirmed/observed/inferred/unknown); токен DOSBox только в env; графику/exe пока не патчим (решение пользователя).
