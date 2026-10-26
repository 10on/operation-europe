# 05. OCR, OpenCV и Qwen-VL на Mac

## Что именно распознавать

Не «смотри видео и играй как человек», а распознавай **состояния экранов и конкретные поля**: меню, текущий сценарий, название подразделения, координаты, пункты приказов, численность, снабжение, изменение после команды, предупреждение об ошибке.

Лучше иметь машинную карту UI: `screen_id -> ROI -> field -> parser -> expected range -> confidence`. Схематичная графика 1990-х позволяет извлечь цифры дешевле, чем большой VLM, но пиксельный шрифт часто плохо подходит готовому Tesseract.

## Каскад обработки

1. Frame PNG в нативном разрешении от DOSBox Automation, без JPEG/фильтров и без VNC.
2. Дедупликация `sha256(frame)` или perceptual hash с маской мигающего курсора.
3. Определение экрана по **template matching/OpenCV** и расположению ключевых элементов (а не только полноэкранному similarity).
4. Вырезка конкретного ROI, upscale nearest neighbor 2x–4x, бинаризация и Tesseract (`--psm 7` для одной строки, `--psm 10` для одного символа, `--psm 6` для блока). Сравнить варианты на наборе вручную размеченных ROI.
5. Для стабильных цифр построить **шаблонный OCR**: эталонные глифы 0–9 и X/Y; это может быть точнее нейросетей.
6. Для неизвестного экрана/ошибки — Qwen-VL на Mac: классификация, описание интерактивных элементов, список ROI для будущих deterministic extractors.
7. При конфликте методов не «голосовать» без оснований. Присвоить `needs_review` и приложить PNG.

## Qwen на Mac M1 Max (64 GB)

Проверенные модели для MLX:

- `mlx-community/Qwen3-VL-4B-Instruct-4bit` — базовый вариант для экранной семантики.
- `mlx-community/Qwen2.5-VL-3B-Instruct-4bit` — более лёгкий fallback.

Наличие модели/совместимость MLX подтверждается карточкой Hugging Face, но скорость, VRAM и точность **на этой игре ещё не измерялись**. Даже 4B-VL может ошибаться на отдельных маленьких цифрах; итоговые игровые значения должны извлекаться OCR/памятью и проверяться. Модель из-за этого *не* получает право на прямое бесконтрольное управление клавиатурой.

Пробный запуск:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip mlx-vlm
python -m mlx_vlm.generate \
  --model mlx-community/Qwen3-VL-4B-Instruct-4bit \
  --max-tokens 180 --temp 0.0 \
  --prompt 'Classify this DOS strategy-game screen. Reply JSON: screen_type, visible_labels, unclear_regions. Do not guess unreadable digits.' \
  --image artifacts/frame.png
```

Если конкретная версия `mlx-vlm` не принимает эти аргументы, свериться с `python -m mlx_vlm.generate --help` и с карточкой модели. Записывать точные версии и модель/revision в отчёт.

## Алгоритм автонавигатора

`state detection -> allowed action list -> one bounded action -> new frame -> assert expected state -> log`. Для каждого экрана заранее фиксировать допустимые клавиши и ожидаемый переход. Если состояние неожиданное, автонавигатор **останавливается**, а не кликает дальше по тексту, который мог галлюцинировать VLM.

### Пример запроса к VLM

```text
You are observing a screenshot from Operation Europe (DOS), not controlling it.
Return JSON only. Identify: screen_type, visible_commands, selected_unit,
uncertain_regions. Never invent unreadable numeric values; use null.
No keyboard suggestions unless the command is explicitly visible.
```

### Пример результата

```json
{
  "screen_type": "unit_details",
  "visible_commands": ["Move", "Attack"],
  "selected_unit": null,
  "uncertain_regions": ["upper_right_numbers"]
}
```

**Пример синтетический**: он не отражает подтверждённый экран игры, названия команд могут отличаться.

## Калибровка и бенчмарк

1. Разметить 50–100 ROI с подтверждёнными значениями, включая 0/6/8/9, пустые клетки и отрицательные/процентные показатели, если они встречаются.
2. Метрики: exact-match поля, character error rate, доля отказов (unknown), число ложных уверенных значений, latency/frame, стоимость запроса (локально/облако).
3. Нацелиться на почти нулевые **ложные уверенные** значения. Лучше 20% `unknown`, чем ошибочный ввод боевых характеристик.
4. Сохранять оригинальный crop и transcript версии VLM; улучшая OCR, не переписывать старые измерения задним числом.

## Что отдать облачному агенту

Не скриншоты подряд. Отчёт содержит `screen_type`, `action`, `before/after`, 2–5 значимых ROI, `evidence_path`, `issue`, `confidence`; небольшой кадр только если сложность семантическая.
