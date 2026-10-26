<!-- schema_version: 1 | processed: 2026-10-26 -->
# Различия платформ: Genesis / SNES / DOS

Что именно прочитано (важно для доверия):
| Источник | Платформа | Прочитано |
|---|---|---|
| GEN-FAQ (War Doc) | Genesis | §6–10, часть §11 |
| `operation-europe-path-to-victory-1939-45-usa__1745.pdf` (вторая копия того же мануала, названная как Genesis, удалена) | **SNES** (67-страничный мануал, лицензия Nintendo, кнопки X/Y/L/R) | выборочно: оглавление, кнопки, Army Commands (Info/Ask/SpFc/Transfer/Orgz/Air), словарь, бой (стр. 40) |
| `snes_manual.pdf` (videogamemanual) | SNES | не открывался (вероятно тот же мануал) |
| `document.pdf` | **DOS** (PC manual draft, 46 стр., 26.08.1996) | полностью, текст извлечён в `private/sources/dos_manual.txt` |
| Genesis-мануал | Genesis | **НЕ получен** — среди присланных файлов его нет |

## Вывод
- **Genesis и SNES** — одно семейство интерфейса: меню Tact / SpFc / Ask / Air / Orgz / Move(Transfer) / Info / Wait; Info = Gnrl|Ofcr, Arms, Vict, Unit, City. Расхождения только в кнопках контроллера (SNES: A/B/X/Y/L/R/Select) — это и подтверждает гипотезу пользователя; полностью парсить SNES-мануал не требуется, достаточно выборочно сверять термины.
- **DOS** — заметно другой интерфейс и частично правила (мышь/клавиатура). Его нельзя смешивать с консольными.

## DOS vs консоли (по тексту)
| Тема | Genesis (FAQ) / SNES | DOS |
|---|---|---|
| Главное меню | Tact, SpFc, Ask, Air, Orgz, Move, Info, Wait; START/Select — опции | Tact, City, Tsfr, Ofcr, Info, Orgz, Rqst, Air, Spfc, Game, Pass |
| Ход времени | Wait N часов | 1 команда-ход = 1 час; Tsfr/Orgz/Rqst/Air/Spfc завершают ход; Pass 1–24 ч |
| Приказы полка | Move, Dfnd, Atck, Sbtg, Sply, Prsu, Ocpy, Rest | Move, Attack, Destroy (мост), Pursue, Occupy, Defend, Supply, Rest; инженеры: Bridge, Mine; снабжение: Repair |
| Типы полков | номер на 8 = снабжение (FAQ) | 4 типа: Assault (≤2), Battle (≤4), Engineer (1), Supply (1) на дивизию, итого ≤8; 1-я цифра номера = дивизия |
| Бой | карта 13×13, команды Move/Attack/Pursue/Retreat/Follow + полк | Move, Attack, Blitz, Defend, Retreat; 10 боевых ходов; победа — разгром цели; ничья по таймеру |
| Таймер боя | не определён | SNES: Battle Clock стартует с 99 (час за единицу); DOS: 10 ходов |
| Спецсилы | Raid, Sbtg, Cut, Elim, Info | Recon, Cut Lines, Sabotage, Raid, Assassinate (Recon — самое лёгкое, Assassinate — самое трудное) |
| Запросы | Ask | Rqst: Supplies / Battalions / Regiments |
| Кто влияет на SpFc/Air | CI — спецсилы (FAQ §7.2) | DOS: CO — спецсилы, CI — авиация (расхождение, см. unverified) |
| Показатели командира | Ldr, Chrm, Inf, Atry, Tank | + Bravery, Health, Experience |
| Сложность | не упомянута | 5 уровней (Very Easy…Very Hard) |
| Карты | одна карта 40×40 | Field Map (1:13 000, скролл) и Aerial Map (1:40 000) |
| Сохранения | Save/Load | 20 слотов |
