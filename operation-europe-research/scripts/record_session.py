#!/usr/bin/env python3
"""Запись сессии ручной игры: события ввода (API input/record) + скриншот при каждом изменении экрана.
Результат: artifacts/experiments/<name>/ {shots/NNN_tXXXXXms.png, events.json, timeline.json}
Запуск:  record_session.py start <name>    (блокирует до флага остановки или Ctrl+C)
Стоп:    record_session.py stop  <name>    (создаёт файл-флаг; рекордер сам завершится и сохранит всё)
Игрок управляет игрой в окне DOSBox; рекордер только наблюдает. Заметки игрока можно писать: record_session.py note <name> "текст"
"""
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import dosbox_ctl as d  # noqa: E402
from PIL import Image, ImageChops  # noqa: E402

OE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def exp_dir(name):
    return os.path.join(OE, "artifacts", "experiments", name)


def small(im):
    return im.convert("L").resize((80, 60))


def changed(a, b, thr=6):
    if a is None:
        return True
    diff = ImageChops.difference(a, b).point(lambda v: 255 if v > 24 else 0)
    return diff.histogram()[255] >= thr


def start(name, interval=0.4):
    base = exp_dir(name)
    shots = os.path.join(base, "shots")
    os.makedirs(shots, exist_ok=True)
    stop_flag = os.path.join(base, "STOP")
    if os.path.exists(stop_flag):
        os.remove(stop_flag)
    try:
        d.call("/input/record/stop", "POST", {})
    except SystemExit:
        pass
    d.call("/input/record/start", "POST", {})
    t0 = time.time()
    timeline, prev, n = [], None, 0
    print(f"запись началась: {base}  (остановка: record_session.py stop {name})", flush=True)
    try:
        while not os.path.exists(stop_flag):
            png = d.call("/video/frame", raw=True)
            im = Image.open(io.BytesIO(png)).convert("RGB")
            sm = small(im)
            if changed(prev, sm):
                n += 1
                ms = int((time.time() - t0) * 1000)
                fn = f"{n:03d}_t{ms:07d}.png"
                im.save(os.path.join(shots, fn))
                st = d.call("/input/record/status")
                prog = d.call("/program/state").get("segment_name", "").strip()
                timeline.append({"shot": fn, "t_ms": ms, "events_so_far": st.get("event_count"), "program": prog,
                                 "size": list(im.size)})
                prev = sm
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    res = d.call("/input/record/stop", "POST", {})
    json.dump(res, open(os.path.join(base, "events.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    notes = []
    nf = os.path.join(base, "notes.jsonl")
    if os.path.exists(nf):
        notes = [json.loads(x) for x in open(nf, encoding="utf-8") if x.strip()]
    json.dump({"started_unix": t0, "shots": timeline, "notes": notes, "event_count": res.get("event_count"),
               "duration_ms": res.get("duration_ms")}, open(os.path.join(base, "timeline.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"готово: {n} скриншотов, {res.get('event_count')} событий ввода -> {base}", flush=True)


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("start", "stop", "note"):
        sys.exit(__doc__)
    cmd, name = sys.argv[1], sys.argv[2]
    base = exp_dir(name)
    if cmd == "start":
        start(name)
    elif cmd == "stop":
        os.makedirs(base, exist_ok=True)
        open(os.path.join(base, "STOP"), "w").write("1")
        print("флаг остановки создан")
    elif cmd == "note":
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "notes.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"unix": time.time(), "text": " ".join(sys.argv[3:])}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
