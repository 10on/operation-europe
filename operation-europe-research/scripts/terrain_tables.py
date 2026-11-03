"""Terrain reference from main.exe: names, movement classes and the six weather movement tables (docs/TERRAIN.md).

- names: pointer table DS:0x3B72 (11 words);
- class of a unit category: DS:0xC11C (used by the movement step 42e6:0008);
- weather tables: 6 x 55 bytes at file 0x40640 (segment 0x3A64 in the load image), copied to DS:0x76 by the
  weather change 1f43:000e as weather * 55. Rows = terrain type (MAPINF cell & 0x0F), columns = class.
DS:X = main.exe file offset 0x4D120 + X. Writes a JSON table; the game file is never written.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS_FILE = 0x4D120
NAMES = 0x3B72
CLASS_MAP = 0xC11C
WEATHER_FILE = 0x3A64 * 16 + 0x6000
WEATHERS = ("Clear", "Cloudy", "Rain", "Snow", "Fog", "Stormy")  # DS:0x3B38
CATEGORIES = ("Infnty", "Mech", "Armor", "Tanks", "Arty", "Enginr", "Repair", "Supply")


def word(exe, ds):
    return int.from_bytes(exe[DS_FILE + ds:DS_FILE + ds + 2], "little")


def cstring(exe, ds):
    start = DS_FILE + ds
    return exe[start:exe.index(b"\0", start)].decode("latin1")


def tables(exe: bytes) -> dict:
    names = [cstring(exe, word(exe, NAMES + 2 * t)) for t in range(11)]
    classes = {c: exe[DS_FILE + CLASS_MAP + i] for i, c in enumerate(CATEGORIES)}
    weather = {}
    for w, wname in enumerate(WEATHERS):
        off = WEATHER_FILE + w * 55
        weather[wname] = dict(file_offset=off, rows={names[t]: list(exe[off + t * 5:off + t * 5 + 5]) for t in range(11)})
    initial = {names[t]: list(exe[DS_FILE + 0x76 + t * 5:DS_FILE + 0x76 + t * 5 + 5]) for t in range(11)}
    return dict(terrain=[dict(type=t, name=n, name_ds=word(exe, NAMES + 2 * t)) for t, n in enumerate(names)],
                class_of_category=classes, class_map_ds=CLASS_MAP, weather_tables=weather,
                initial_table_ds=0x76, initial_table=initial, scale_ds=0x49, scale=exe[DS_FILE + 0x49])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", type=Path, default=ROOT / "private/game-dos-working/main.exe")
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts/experiments/TERRAIN-67-20261103/terrain.json")
    a = ap.parse_args(argv)
    exe = a.exe.read_bytes()
    data = dict(source="main.exe", sha256=hashlib.sha256(exe).hexdigest(), **tables(exe))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(dict(terrain=len(data["terrain"]), weathers=len(data["weather_tables"]), out=str(a.out))))


if __name__ == "__main__":
    main()
