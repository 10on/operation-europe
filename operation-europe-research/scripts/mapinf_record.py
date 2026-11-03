"""Lossless MAPINF.DAT parser: 6 regions x 1600 bytes, each read as a 40x40 grid of cells.

Region i is read for scedata selector&127 == i (runtime for 0..2). The 40x40 shape and the
cell split (code = low 7 bits, flag = bit 7) are inferred from byte statistics; semantics unknown.
"""
from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGION_SIZE = 1600
WIDTH = 40


@dataclass(frozen=True)
class Region:
    rows: tuple  # 40 rows of 40 raw cell bytes

    @classmethod
    def parse(cls, raw):
        if len(raw) != REGION_SIZE: raise ValueError('Region must contain 1600 bytes')
        return cls(tuple(raw[n:n + WIDTH] for n in range(0, REGION_SIZE, WIDTH)))

    def cell(self, x, y):
        b = self.rows[y][x]
        return b & 0x7F, bool(b & 0x80)

    def build(self):
        if len(self.rows) != REGION_SIZE // WIDTH or any(len(r) != WIDTH for r in self.rows):
            raise ValueError('Invalid grid shape')
        return b''.join(self.rows)


@dataclass(frozen=True)
class Mapinf:
    regions: tuple

    @classmethod
    def parse(cls, raw):
        if not raw or len(raw) % REGION_SIZE: raise ValueError('Invalid MAPINF framing')
        return cls(tuple(Region.parse(raw[n:n + REGION_SIZE]) for n in range(0, len(raw), REGION_SIZE)))

    def build(self):
        return b''.join(r.build() for r in self.regions)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=ROOT / 'private/game-dos-working/mapinf.dat')
    a = ap.parse_args()
    raw = a.source.read_bytes()
    m = Mapinf.parse(raw)
    print(json.dumps(dict(regions=len(m.regions), round_trip_equal=m.build() == raw,
                          sha256=hashlib.sha256(raw).hexdigest())))
