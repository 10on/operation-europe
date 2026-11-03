"""Lossless MAPPNO.DAT parser: same framing as MAPINF.DAT (6 regions x 1600 bytes, 40x40 cells).

Runtime reads of 1600 bytes at i*1600 per scenario are logged in knowledge/FILE_MAP.md (IOLOG-20261031).
Cell byte = value 0..79; 0 coincides with MAPINF code 3 cells. Meaning unknown.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapinf_record import Mapinf as Mappno, Region, REGION_SIZE, WIDTH  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=ROOT / 'private/game-dos-working/mappno.dat')
    raw = ap.parse_args().source.read_bytes()
    m = Mappno.parse(raw)
    print(json.dumps(dict(regions=len(m.regions), round_trip_equal=m.build() == raw, sha256=hashlib.sha256(raw).hexdigest())))
