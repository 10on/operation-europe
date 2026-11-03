"""Unit type (equipment) reference from main.exe: 158 records of 13 bytes at DGROUP DS:0x3332.

Index = regiment type byte (scedata/save regiment +2): code computes type*13 + 0x3332 (e.g. file 0x7b78..0x7b88,
0x1290d..0x12923 in the code image). Field meanings: docs/UNIT_TYPES.md. DS:X = main.exe file offset 0x4D120 + X.
Writes a JSON table; the game file itself is never written.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS_FILE = 0x4D120
TABLE = 0x3332
SIZE = 13
COUNT = 158
NATIONS = ("GER", "ITY", "USA", "ENG", "FRN", "RUS")  # bit order of +2, as the name strings at DS:0x2CA0
CATEGORIES = ("Infnty", "Mech", "Armor", "Tanks", "Arty", "Enginr", "Repair", "Supply")  # +4, army summary


def cstring(exe: bytes, ds: int) -> str:
    start = DS_FILE + ds
    return exe[start:exe.index(b"\0", start)].decode("latin1")


def records(exe: bytes):
    for t in range(COUNT):
        off = DS_FILE + TABLE + t * SIZE
        r = exe[off:off + SIZE]
        name_ptr = int.from_bytes(r[0:2], "little")
        yield dict(
            type=t, file_offset=off, ds=TABLE + t * SIZE, name=cstring(exe, name_ptr), name_ds=name_ptr,
            nations=[n for i, n in enumerate(NATIONS) if r[2] >> i & 1], nation_mask=r[2], b3=r[3],
            category=CATEGORIES[r[4]] if r[4] < len(CATEGORIES) else r[4], at=r[5], ap=r[6], defense=r[7],
            speed=r[8], b9=r[9], b10=r[10], m_rng=r[9] * r[10] // 10, g_rng=r[11], b12=r[12])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", type=Path, default=ROOT / "private/game-dos-working/main.exe")
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts/experiments/UNITTYPES-64-20261103/unit_types.json")
    a = ap.parse_args(argv)
    exe = a.exe.read_bytes()
    rows = list(records(exe))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(source="main.exe", sha256=hashlib.sha256(exe).hexdigest(), records=rows),
                                indent=1) + "\n", encoding="utf-8")
    print(json.dumps(dict(records=len(rows), out=str(a.out))))


if __name__ == "__main__":
    main()
