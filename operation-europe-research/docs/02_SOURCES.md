# 02. Исходные сведения и проверенные ссылки

Состояние на 2026-10-25. Ссылки — источники ориентиров, а не доказательство устройства конкретного EXE. НЕ скачивать из интернета исполняемые файлы с непроверенных зеркал в автоматическом режиме.

## По игре

1. MobyGames: Operation Europe: Path to Victory 1939–45 — https://www.mobygames.com/game/1934/operation-europe-path-to-victory-1939-45/ . Указывает разработчика/издателя Koei, DOS-релиз 1994, Genesis 1993/1994 и другие платформы. Это подтверждает существование разных версий, не идентичность их алгоритмов.
2. MobyGames releases — https://www.mobygames.com/game/1934/operation-europe-path-to-victory-1939-45/releases/ . Уточнение регионов/дат.
3. Neoseeker Hex Dump (War Doc, 2004, Genesis) — https://www.neoseeker.com/operation-europe/faqs/72509-dump.html . Содержит строки/описания ROM Genesis, примеры экранных надписей/имён; **не** таблица адресов для DOS и **не** готовые исходники.
4. Neoseeker FAQ index — https://www.neoseeker.com/operation-europe/faqs/ . Есть руководство по стратегии для Genesis (War Doc, 2004). Полезно собрать список терминов, правил, команд.
5. Koei Tecmo Wiki — https://koeitecmo.wiki/wiki/Operation_Europe%3A_Path_to_Victory . Вторичный каталог изданий; отдельно отмечает поздний Windows-релиз в Японии, который не стоит путать с DOS.

## Инструменты

1. DOSBox Automation (код/версии) — https://github.com/dosbox-automation/dosbox-automation
2. Документация API 0.85.1 — https://www.dosbox-automation.org/0.85.1/automation/rest-api/index.html
3. Веб-сервер и безопасность — https://www.dosbox-automation.org/0.85.1/automation/webserver/index.html
4. DOSBox-X отладчик — https://github.com/joncampbell123/dosbox-x/blob/master/README.debugger
5. Ghidra Headless Analyzer — https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md
6. Ghidra MZ parser (API) — https://ghidra.re/ghidra_docs/api/ghidra/app/util/bin/format/mz/MzExecutable.html
7. Tesseract OCR CLI — https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html
8. MLX model Qwen3-VL-4B-Instruct-4bit — https://huggingface.co/mlx-community/Qwen3-VL-4B-Instruct-4bit
9. Альтернативная MLX модель Qwen2.5-VL-3B-Instruct-4bit — https://huggingface.co/mlx-community/Qwen2.5-VL-3B-Instruct-4bit

## Что здесь намеренно не утверждается

- Не получены DOS-оригиналы и не установлены имена файла EXE, тип сжатия, формат таблиц или адреса структуры дивизии.
- Не подтверждено, что какие-либо данные из ROM совпадают байт-в-байт с DOS.
- Не подтверждено, что алгоритм боя состоит только из таблиц (скорее всего есть код выбора веток, RNG, события, AI).
- Не подтверждено, что конкретный дистрибутив можно без настройки сразу импортировать в Ghidra. Для DOS MZ есть поддержка, но overlays/protection/packers влияют на результат.
- Отсутствие современной коммерческой продажи не означает прекращения авторских прав; «abandonware» не юридический статус лицензии.

## Вопросы к исследованию

- Какая именно версия и язык DOS-дистрибутива? Есть ли несколько EXE, оверлеи, data-файлы, установщик?
- Меняются ли системные файлы/сохранения при игре?
- Какие конкретно числа с экрана (оружие, сила, снабжение) доступны для тестовых поисков в дампе?
- Можно ли установить известный reference сценарий на Sega для сравнения с DOS?
