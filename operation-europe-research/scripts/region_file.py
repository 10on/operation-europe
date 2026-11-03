"""Lossless parser for per-scenario region files: the game reads one fixed-size region per scenario
at i*size (IOLOG-20261031, knowledge/FILE_MAP.md). Region contents stay raw bytes here.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGION_SIZES = {'bigmap.dat': 3072, 'midmap.dat': 27648, 'hexdisp.dat': 1600, 'mapinf.dat': 1600, 'mappno.dat': 1600}


def parse(raw, size):
    if not raw or len(raw) % size: raise ValueError('Invalid region framing')
    return [raw[n:n + size] for n in range(0, len(raw), size)]


def build(regions, size):
    if any(len(r) != size for r in regions): raise ValueError('Invalid region size')
    return b''.join(regions)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('name', choices=sorted(REGION_SIZES))
    ap.add_argument('--dir', type=Path, default=ROOT / 'private/game-dos-working')
    a = ap.parse_args()
    raw = (a.dir / a.name).read_bytes()
    size = REGION_SIZES[a.name]
    regs = parse(raw, size)
    print(json.dumps(dict(file=a.name, regions=len(regs), region_size=size, round_trip_equal=build(regs, size) == raw,
                          sha256=hashlib.sha256(raw).hexdigest())))
