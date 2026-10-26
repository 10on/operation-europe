# 09. Mac M1 Max — Vision и агрегация фактов

## Задачи Mac

Mac — не второй эмулятор для игры и не повторение статического анализа. Он получает кадры из Windows, распознаёт структуру UI через дешёвые методы, при надобности Qwen-VL, связывает результаты с задачами и формирует короткий отчёт для cloud reviewer.

## Стартовое окружение

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip mlx-vlm pillow
```

При желании `brew install tesseract`, `pip install opencv-python`; это необязательные зависимости и лучше изолировать в отдельном окружении. Ожидаемая модель: `mlx-community/Qwen3-VL-4B-Instruct-4bit` (действительно доступна в MLX). Fallback: `mlx-community/Qwen2.5-VL-3B-Instruct-4bit`.

## Проверка одной картинки

```bash
python -m mlx_vlm.generate \
  --model mlx-community/Qwen3-VL-4B-Instruct-4bit \
  --max-tokens 120 --temp 0.0 \
  --prompt 'Identify interface state and labels. Return unknown for unreadable digits.' \
  --image /path/to/frame.png
```

Сначала один кадр, измерить время, память, точность. Если модель упорно неправильно читает цифры, оставить ей только классификацию UI, а цифры дать шаблонному распознаванию или памяти DOS.

## SSH tunnel (только если нужен live API)

```bash
ssh -N -L 18386:127.0.0.1:8386 windows-user@windows-host
```

В другом терминале Mac:

```bash
export DOSBOX_API_URL=http://127.0.0.1:18386
export DOSBOX_API_TOKEN='ваш_локальный_токен'
python scripts/dosbox_api.py status
```

По умолчанию **не** отдавать Qwen управление клавиатурой в live loop. Qwen возвращает только структурированный ответ наблюдателя, Windows-агент валидирует команду перед выполнением.

## Передача кадров без live API

Windows сохраняет `artifacts/experiments/EXP-001/before.png`; Mac получает SCP/SMB-копию. Если применён `scp`, путь Windows OpenSSH может зависеть от shell и настроек; проверить вручную первую передачу. VNC используется для диагностики редких GUI-проблем, не как постоянный канал распознавания.

## Пакет для облачного ревью

Собрать один Markdown summary, пару эталонных ROI и CSV/JSON наблюдений, а не 3000 изображений. Включить спорные гипотезы и конкретные следующие измерения.
