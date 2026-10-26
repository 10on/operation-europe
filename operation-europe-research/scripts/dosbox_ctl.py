#!/usr/bin/env python3
"""Управление DOSBox Automation 0.85.1: клавиатура, мышь, текст экрана, скриншот, CPU/память.
Только loopback; токен из DOSBOX_API_TOKEN. Примеры:
  dosbox_ctl.py run "d:" ; dosbox_ctl.py run mousetest
  dosbox_ctl.py key KBD_enter | keys KBD_esc KBD_enter
  dosbox_ctl.py mouse-home ; mouse-move 95 211 ; click [left|right|middle] ; mouse-to X Y  (абсолютные координаты экрана игры: home + масштаб --sx/--sy)
  dosbox_ctl.py text ; shot out.png ; cpu ; mem SEG OFF LEN
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("DOSBOX_API_URL", "http://127.0.0.1:8386").rstrip("/") + "/api/v1"
TOKEN = os.getenv("DOSBOX_API_TOKEN", "")


def call(path, method="GET", body=None, raw=False):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", TOKEN):
        sys.exit("DOSBOX_API_TOKEN отсутствует (. .\\scripts\\env.ps1)")
    if not BASE.startswith(("http://127.0.0.1:", "http://localhost:")):
        sys.exit("Только loopback")
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    for attempt in range(60):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
                return data if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            msg = e.read(300).decode("utf-8", "replace")
            if "Replay already in progress" in msg or "No frame available" in msg:   # ввод ещё играет / кадра пока нет
                time.sleep(0.25)
                continue
            sys.exit(f"HTTP {e.code}: {msg}")
    sys.exit("Replay не завершился")


def seq(events):
    return call("/input/sequence", "POST", {"events": events})


def key(name, hold_ms=60):
    seq([{"type": "key", "key": name, "pressed": True},
         {"type": "key", "key": name, "pressed": False, "delay_ms": hold_ms}])


def type_text(text, cps=25):
    call("/input/type", "POST", {"text": text, "cps": cps})
    time.sleep(len(text) / cps + 0.4)


def mouse_move(dx, dy, step=120):
    """Относительное движение порциями (большие дельты могут обрезаться драйвером)."""
    evs = []
    while abs(dx) > step or abs(dy) > step:
        sx = max(-step, min(step, dx))
        sy = max(-step, min(step, dy))
        evs.append({"type": "mouse_move", "x_rel": sx, "y_rel": sy, "delay_ms": 15})
        dx -= sx
        dy -= sy
    evs.append({"type": "mouse_move", "x_rel": dx, "y_rel": dy, "delay_ms": 15})
    seq(evs)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("run"); s.add_argument("text")
    s = sub.add_parser("type"); s.add_argument("text")
    s = sub.add_parser("key"); s.add_argument("name")
    s = sub.add_parser("keys"); s.add_argument("names", nargs="+")
    sub.add_parser("mouse-home")
    s = sub.add_parser("mouse-move"); s.add_argument("dx", type=float); s.add_argument("dy", type=float)
    s = sub.add_parser("mouse-to"); s.add_argument("x", type=float); s.add_argument("y", type=float)
    s.add_argument("--sx", type=float, default=1.0); s.add_argument("--sy", type=float, default=2.0)   # INT33 по умолчанию: 8:16 мик/пикс -> Y вдвое медленнее
    s = sub.add_parser("click"); s.add_argument("button", nargs="?", default="left", choices=["left", "right", "middle"])
    sub.add_parser("text"); sub.add_parser("cpu"); sub.add_parser("state")
    s = sub.add_parser("shot"); s.add_argument("out")
    s = sub.add_parser("mem"); s.add_argument("seg"); s.add_argument("off"); s.add_argument("length", type=int)
    a = p.parse_args()
    if a.cmd == "run":
        type_text(a.text); key("KBD_enter")
    elif a.cmd == "type":
        type_text(a.text)
    elif a.cmd == "key":
        key(a.name)
    elif a.cmd == "keys":
        for n in a.names:
            key(n); time.sleep(0.15)
    elif a.cmd == "mouse-home":
        mouse_move(-4000, -4000)
    elif a.cmd == "mouse-move":
        mouse_move(a.dx, a.dy)
    elif a.cmd == "mouse-to":
        mouse_move(-4000, -4000); time.sleep(0.2); mouse_move(a.x * a.sx, a.y * a.sy)
    elif a.cmd == "click":
        seq([{"type": "mouse_button", "button": a.button, "pressed": True},
             {"type": "mouse_button", "button": a.button, "pressed": False, "delay_ms": 120}])
    elif a.cmd == "text":
        t = call("/video/text")
        txt = t["text"]
        for line in txt.split("\n"):
            try:
                line = line.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
            print(line.rstrip())
    elif a.cmd == "cpu":
        r = call("/cpu/state")["registers"]
        print(" ".join(f"{k}={v:x}" for k, v in r.items()))
    elif a.cmd == "state":
        print(json.dumps(call("/program/state")), json.dumps(call("/video/frame/info").get("video_mode")))
    elif a.cmd == "shot":
        d = call("/video/frame", raw=True)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        open(a.out, "wb").write(d); print(f"{len(d)} bytes -> {a.out}")
    elif a.cmd == "mem":
        d = call(f"/memory/{a.seg}/{a.off}/{a.length}", raw=True)
        print(d.hex())


if __name__ == "__main__":
    main()
