# DOS: путь от меню до карты (по записи PLAY-001, 2026-10-26)
Источник: ручное прохождение игрока, записанное рекордером (`artifacts/experiments/PLAY-001`: 61 скриншот, 3082 события ввода, 90 с; `timeline.json` связывает кадры со временем).
Статус: observed. Координаты — пиксели экрана 640×480 (режим 12h) с контактных листов, ±5 px; мышь двигать как в DOS_INPUT.md (home, затем x, 2·y).
Шум: в записи ~2950 событий `mouse_move` — случайные движения мыши, их игнорировать; значимы только 32 клика левой кнопкой и смена экранов.

## Последовательность экранов (сценарий «Invasion of France», 1 игрок, Allies)
| # | Экран (кадр) | Текст/заголовок | Действие игрока | Координаты клика |
|---|---|---|---|---|
| 1 | 001 | New Game / Load Game | New Game | (80,211) |
| 2 | 002 | Which scenario will you play? (6 пунктов) | Invasion of France | (150,195); пункты шагом 24 по Y: France 195, N.Africa 219, Kursk 243, Normandy 267, Bulge 291, Berlin 315 |
| 3 | 003–006 | текст предыстории (история сценария) | клик в любом месте листа (внизу курсор-«мышка» = ждёт клика) | любое |
| 4 | 007 | How many players? | One Player | Demo (80,211), One Player (80,235), Two Players (80,259) |
| 5 | 008 | Which side will you command? | The Allies | Allies (80,211), Axis (80,235) |
| 6 | 009–017 | Which map will you use? | Field Map | Field (80,211), Aerial (80,235) |
| 7 | 018 | View Battles? | View all battles (запись: «View All Battles») | View (100,211), Don't View (100,235), Choose at Battle (100,259) |
| 8 | 019 | Select Difficulty Level | Very Easy | Very Easy (100,211), Easy 235, Average 259, Hard 283, Very Hard 307 |
| 9 | 020–024 | Are the settings OK? (значок мыши = ждёт клика) | подтвердить — левый клик (правый — отмена, по тексту DOS-мануала) | любое |
| 10 | 025–047 | экран офицеров «The Allied Army» (синий фон): Ops Chief / Army Cmndr / Intl Chief, Div 1–4, таблица Lead/Chrm/Bryv/Hlth/Infy/Arty/Tank | Правый клик — перебросить способности, левый — зафиксировать. Затем по подсказкам внизу выбирать строки таблицы (строки Y≈297,314,332,349,367,383, X≈190): Who will you play? (Army Cmndr) → Ops Chief → Intl Chief → Div 1 → Div 2 → Div 3 → Div 4 | в записи выбраны: Corap (AC), Bauxdey (Ops), La Fontaine (Intl), de Gaulle (Div 1), Bruno (Div 2), Brogado (Div 3), Banaux (Div 4; список прокручивался) |
| 11 | 039–046 | Are you satisfied with the Div 4 Commander selection? / Use these generals? | левый клик (значок мыши) | любое |
| 12 | 048 | Are you ready for battle? (синяя полоса) | левый клик | любое |
| 13 | 049–051 | загрузка: заголовок «BLITZKRIEG 5.10.40 00:00 Clear» | ждать | — |
| 14 | 052–058 | сообщения Supreme Commander (Eisenhower) и Chief of Staff (Smith) — 6–7 реплик | по клику листать реплики (значок в углу окна реплики) | клики в окне реплики |
| 15 | 059–061 | «Allied Regiment 11 Battle executing orders»; затем карта стратегии | при необходимости клик; итог: **стратегический экран** | — |

## Стратегический экран (кадр 061)
- Верхняя строка меню (y≈50): **Pass, Tact, City, Tsfr, Ofcr, Info, Orgz, Rqst, Air, SpFc, Game** — совпадает с DOS-мануалом (11 команд).
- Слева карта (Field Map, масштаб 1:130000), справа три блока: данные Army Cmdr (Leader/Charm/Bryv/Health, Inf/Arty/Tanks/Exp), блок «Allied» (Tanks 217, Infnty 12811, Armor 255, Enginr 212, Mech 390, Supply 762, Arty 411, Repair 425; Fuel 89%, Ammo 69%, Food 70%; Bmbrs 100, Cargo 100, Cities 11, Paratp 0, Land 66%, Air 20%), блок «Ops Chief: Bauxdey» с репликой.
- Заголовок: «BLITZKRIEG 5.10.40 00:00 Clear» (дата 5.10.40, 00:00, погода Clear).
- После выбора сценария Normandy/France и т.д. заголовок и данные другие — не проверено.

## Что дальше можно сделать с этим
1. `oe-boot newgame` — автоматический проход по таблице выше (координаты из этой записи; выбор офицеров — по строкам таблицы). Не реализовано.
2. Проход через «правый клик — перебросить способности» (случайные значения) — поведение рандома не проверялось.
3. Сохранения/Load Game — не проходились.

## Что не подтверждено
- Точные координаты клика на «Are the settings OK?/Use these generals?/Are you ready…» — клик по любому месту, но не проверено, что правая кнопка = «нет».
- Какая именно реплика пропускается при каком клике (кадры 052–058: 7 реплик за ~4 с, игрок кликал быстро).
- Прокрутка списка офицеров (стрелки ∧/∨ у таблицы).
