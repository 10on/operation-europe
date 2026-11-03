"""Memory-write watch in DOSBox-X: load a SAVEDATA slot by AUTOTYPE, pass time, log every write to given DS offsets.

Usage (from operation-europe-research/):
  python -I scripts/dosboxx_watch.py --slot 1 --hours 12 --watch 17BE 17BF --experiment MOVE-226-20261103

- The game starts under the DOSBox-X debugger (DEBUGBOX MAIN, config from TASK-008); commands go over the loopback
  control port 58993 (artifacts/experiments/TASK-008/probe_debugger.py, Control).
- Keys are typed by AUTOTYPE: skip logo, Load Game, slot, ready, Pass <hours>. The save must already hold the orders.
- BPM <DS>:<off> stops after an instruction changes the byte. DS = load base + 0x4712 (hub knowledge bin:0b33be2f:ds).
- Each hit: registers, Ghidra address (seg + 0x1000 - base), 32 code bytes at CS:IP-16, byte value. Written to
  artifacts/experiments/<id>/hits.json. The EXE runs only inside DOSBox-X; the working copy is not modified.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "private"
GAME = PRIVATE / "game-dos-working/main.exe"
EXE_SHA = "0b33be2fd37b965e5b92d1881f34226c1608eff6d0358787a7cb5049f218e9df"
PORT = 58993
DS_FROM_BASE = 0x4712

spec = importlib.util.spec_from_file_location("native_probe", ROOT / "artifacts/experiments/TASK-008/probe_debugger.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def keys_for(slot, hours):
    # logo, New/Load menu -> Load Game, slot list (cursor on No.1), "ready for battle?", orders prompt -> Pass,
    # hours, "We'll wait N hours ...?" confirmation
    return ["space", "down", "enter"] + ["down"] * slot + ["enter", "enter", "enter"] + list(str(hours)) + ["enter", "enter"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slot", type=int, default=0, help="0-based save slot")
    ap.add_argument("--hours", type=int, default=12)
    ap.add_argument("--watch", nargs="+", required=True, help="DS offsets in hex")
    ap.add_argument("--experiment", required=True)
    ap.add_argument("--wait", type=int, default=10, help="AUTOTYPE initial wait, s")
    ap.add_argument("--pause", type=int, default=4, help="AUTOTYPE pause between keys, s")
    ap.add_argument("--seconds", type=int, default=240, help="how long to collect hits")
    ap.add_argument("--max-hits", type=int, default=60)
    ap.add_argument("--poll", type=float, default=3.0, help="seconds between register polls (each poll briefly stops the emulator)")
    ap.add_argument("--frames", action="store_true", help="save a small desktop frame every 10 s (debugging key timing)")
    a = ap.parse_args()
    if hashlib.sha256(GAME.read_bytes()).hexdigest() != EXE_SHA:
        raise SystemExit("working main.exe differs from the expected version")
    out = ROOT / "artifacts/experiments" / a.experiment
    out.mkdir(parents=True, exist_ok=True)
    config = (ROOT / "artifacts/experiments/TASK-008/dosboxx-task008.conf").read_text(encoding="utf-8")
    config = config.replace("TASK-008", a.experiment).replace("58991", str(PORT))
    keys = " ".join(keys_for(a.slot, a.hours))
    config = config.replace("DEBUGBOX MAIN", f"AUTOTYPE -w {a.wait} -p {a.pause} {keys}\nDEBUGBOX MAIN")
    cfg = PRIVATE / "dosboxx-watch.conf"
    cfg.write_text(config, encoding="utf-8")
    (out / "config.conf").write_text(config, encoding="utf-8")
    hits, log = [], []

    with socket.socket() as server:
        server.bind(("127.0.0.1", PORT)); server.listen(1); server.settimeout(30)
        with (out / "emulator.log").open("w", encoding="utf-8") as elog:
            env = os.environ.copy(); env.pop("SDL_VIDEODRIVER", None)
            startup = subprocess.STARTUPINFO(); startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 5  # visible window: a minimized one breaks AUTOTYPE
            proc = subprocess.Popen([r"C:\DOSBox-X\dosbox-x.exe", "-conf", cfg.name, "-fastlaunch", "-nopromptfolder"],
                                    cwd=PRIVATE, env=env, startupinfo=startup,
                                    creationflags=subprocess.CREATE_NEW_CONSOLE)  # the debugger needs its own console
            timer = threading.Timer(a.seconds + 120, proc.terminate); timer.daemon = True; timer.start()
            try:
                state = {}

                def connect():
                    c, peer = server.accept()
                    if peer[0] != "127.0.0.1":
                        raise RuntimeError("non-loopback peer")
                    state["conn"], state["ctl"] = c, native.Control(c)

                def call(cmd):
                    r = state["ctl"].call(cmd, timeout=10)
                    log.append(r)
                    if r["status"] != "OK":
                        raise RuntimeError(f"debugger rejected {cmd}: {r}")
                    return r

                def regs():
                    names = "CS IP DS SS SP BP AX BX CX".split()
                    v = call("EXEC EV " + " ".join(names))["lines"][-1].split()
                    r = dict(zip(names, (int(x, 16) for x in v)))
                    v = call("EXEC EV DX SI DI ES")["lines"][-1].split()
                    r.update(zip("DX SI DI ES".split(), (int(x, 16) for x in v)))
                    return r

                connect()
                for _ in range(8):  # the link is re-opened when DEBUGBOX MAIN starts
                    time.sleep(3)
                    try:
                        entry = regs()
                        break
                    except (TimeoutError, ConnectionError, OSError):
                        state["conn"].close()
                        connect()
                else:
                    raise RuntimeError("debugger did not answer")
                if entry["IP"] != 0x409C:
                    raise RuntimeError(f"not at verified MZ entry: {entry}")
                if True:
                    base = entry["CS"]
                    ds = base + DS_FROM_BASE
                    for off in a.watch:
                        call(f"EXEC BPM {ds:04X}:{int(off, 16):04X}")
                    call("EXEC RUN")
                    deadline = time.monotonic() + a.seconds
                    started = time.monotonic()
                    if a.frames:
                        from PIL import ImageGrab

                        def frames():
                            while time.monotonic() < deadline and proc.poll() is None:
                                k = int(time.monotonic() - started)
                                ImageGrab.grab().convert("L").resize((480, 270)).save(out / f"frame-{k:03d}.png")
                                time.sleep(10)
                        threading.Thread(target=frames, daemon=True).start()
                    prev, last_vals, timeline, n = None, None, [], 0

                    def dump(off, size):
                        nonlocal n
                        n += 1
                        name = f"WATCH{n:05d}.bin"
                        call(f"EXEC MEMDUMPBIN {ds:04X}:{off:04X} {size:04X} {name}")
                        raw = (PRIVATE / name).read_bytes(); (PRIVATE / name).unlink()
                        return raw

                    while time.monotonic() < deadline and len(hits) < a.max_hits:
                        time.sleep(a.poll)
                        cur = regs()
                        vals = {off: dump(int(off, 16), 1)[0] for off in a.watch}
                        clock = list(dump(0x43, 5))  # selector, year-1940, month, day, hour
                        if not timeline or timeline[-1]["clock"] != clock:
                            timeline.append(dict(t=round(time.monotonic(), 1), clock=clock, ghidra=f"{cur['CS'] - base + 0x1000:04x}:{cur['IP']:04x}"))
                            (out / "timeline.json").write_text(json.dumps(timeline, indent=1), encoding="utf-8")
                        stopped = cur == prev
                        prev = cur
                        if not stopped:
                            continue
                        if vals == last_vals:  # equal registers in an idle loop, not a breakpoint
                            call("EXEC RUN")
                            prev = None
                            continue
                        n += 1
                        name = f"WATCH{n:05d}.bin"
                        call(f"EXEC MEMDUMPBIN {cur['CS']:04X}:{max(cur['IP'] - 16, 0):04X} 0020 {name}")
                        code = (PRIVATE / name).read_bytes(); (PRIVATE / name).unlink()
                        stack = {}
                        for reg in ("SP", "BP"):
                            n += 1
                            sname = f"WATCH{n:05d}.bin"
                            call(f"EXEC MEMDUMPBIN {cur['SS']:04X}:{cur[reg]:04X} 0020 {sname}")
                            stack[reg] = (PRIVATE / sname).read_bytes().hex(); (PRIVATE / sname).unlink()
                        hit = dict(registers=cur, load_base=base, stack=stack, ghidra=f"{cur['CS'] - base + 0x1000:04x}:{cur['IP']:04x}",
                                   code_from_ip_minus_16=code.hex(), values=vals, before=last_vals, clock=clock)
                        last_vals = vals
                        hits.append(hit)
                        (out / "hits.json").write_text(json.dumps(hits, indent=1), encoding="utf-8")
                        print(json.dumps(dict(hit=len(hits), ghidra=hit["ghidra"], values=vals, clock=clock)), flush=True)
                        call("EXEC RUN")
                        prev = None
            finally:
                timer.cancel()
                if proc.poll() is None:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                (out / "commands.json").write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8")
                ok = hashlib.sha256(GAME.read_bytes()).hexdigest() == EXE_SHA
                (out / "session.json").write_text(json.dumps(dict(hits=len(hits), exe_unchanged=ok, keys=keys), indent=1),
                                                  encoding="utf-8")
    print(json.dumps(dict(finished=True, hits=len(hits), evidence=str(out))))


if __name__ == "__main__":
    main()
