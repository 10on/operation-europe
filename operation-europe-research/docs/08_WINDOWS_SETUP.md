# 08. Windows — установка и запуск стенда

Целевое железо: i7-4790K / 32 ГБ DDR3 / RTX A2000 8 ГБ. Для DOS/Ghidra в первую очередь задействован CPU и ОЗУ; карта A2000 не нужна для декомпиляции.

## Каталоги

Пример корня `C:\OE` (репозиторий там же):

```powershell
New-Item -ItemType Directory -Force C:\OE\private\game-dos, C:\OE\private\game-dos-working, C:\OE\artifacts, C:\OE\ghidra-projects
```

**Важно:** распаковывая этот ZIP, разместить файлы именно в `C:\OE` либо заменить рабочие пути во всех примерах. Оригинал хранить в `private\game-dos`, копию для эмулятора в `private\game-dos-working`. Не запускать DOS-EXE прямым запуском в Windows; только DOS-эмуляция.

## Софт

1. Python 3.11+ (x64), Git.
2. Ghidra с поддерживаемой ей версией Java — сверить релизные требования, они меняются.
3. DOSBox Automation по официальным release-архивам (https://github.com/dosbox-automation/dosbox-automation/releases). Документы ниже ориентируются на API **0.85.1**, а не на все версии.
4. DOSBox-X сборка с отладчиком (https://dosbox-x.com/). Перед использованием проверить `DEBUGBOX`/debugger shortcut.
5. По желанию Tesseract OCR 5 и OpenCV Python, если OCR будет на Windows.

Не устанавливать всё разом непроверенными PowerShell install-скриптами. Скачать с официальных источников и зафиксировать версии.

## Шаг W1 — инвентаризация

```powershell
cd C:\OE
py -3 scripts\inventory.py private\game-dos --out artifacts\inventory.json
Get-Content artifacts\inventory.json | Select-Object -First 50
```

Затем `docs/03_STATIC_ANALYSIS.md`: определить MZ/COM и entry point. Не импортировать в Ghidra гипотетический `GAME.EXE`, пока не найден реальный.

## Шаг W2 — config DOSBox Automation

Сгенерировать конфиг установленной программы, добавить `[webserver]` из `config/dosbox-automation.example.conf` и оставить только loopback.

В PowerShell задавать токен в переменной *текущей сессии* (для удобства разработки лучше использовать безопасное хранение/временный файл с ограниченными правами):

```powershell
$env:DOSBOX_API_TOKEN = '<случайная_64_hex_строка>'
# Запустить DOSBox Automation с тем же окружением и включённым webserver.
py -3 scripts\dosbox_api.py info
py -3 scripts\dosbox_api.py screenshot artifacts\smoke.png
```

Токен не выводить в Markdown, issues, текстовые логи и Git. Для постоянных запусков можно использовать `webserver_token_file` по официальной документации.

Открыть `http://127.0.0.1:8386/api.html`; если приходит HTTP 401 на программный запрос — сервер работает, но токен не совпадает.

## Шаг W3 — видео и команды

Сделать скриншот без загрузки игры, затем отдельно повторить после запуска. Убедиться, что размер соответствует игре. Игра может требовать установщик или дополнительный mount; не угадывать имя .EXE.

## Шаг W4 — Ghidra

Импортировать **один** распознанный EXE через GUI, проверить loader/16-bit, сегменты и entry. Только после этой проверки запустить `analyzeHeadless.bat` для серии. Не доверять успешному завершению analyzer как доказательству корректной реконструкции.

## Шаг W5 — доступ с Mac

Включить Windows OpenSSH Server (если доступен), ключи, firewall доступ только из LAN; тест `ssh windows-user@windows-host` с Mac. `ssh -L 18386:127.0.0.1:8386 windows-user@windows-host` на Mac позволяет обращаться к API через `127.0.0.1:18386`, токен сохраняется. SMB/SFTP используем для кадров и JSON, а не для гонки за live GUI.

## Stop conditions

Остановить автоматизацию при порче сохранения, расхождении SHA-256 оригинала, самовольном обращении к внешним сайтам за «EXE fixer» или неожиданной модификации файла в `private/game-dos`.
