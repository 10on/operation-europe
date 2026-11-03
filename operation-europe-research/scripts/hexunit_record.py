"""HEXUNIT.DAT: planar EGA unit sprites. Layout from 3864:10d2 / 3864:0e5e (record 0x28A) and 3a96:000a.

See docs/HEXUNIT_FORMAT.md. The file is read whole (0x8660 bytes) into segment [DS:D0F6] by 16db:0752.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIG_SIZE = 650      # 0x28A: 0x208 bytes of planes, then 0x82 bytes of mask
BIG_COUNT = 52      # index = (3864:0cc0 result) * 4 + DL
SMALL_OFFSET = 33800  # 0x8408, used by 3a96:000a together with 0x8534
SMALL_SIZE = 300
FILE_SIZE = 34400


@dataclass(frozen=True)
class Sprite:
    width: int
    height: int
    planes: bytes  # rows of 4 planes x width/8 bytes (row-interleaved, as 1000:34b8 copies them)
    mask: bytes    # rows of width/8 bytes

    def plane_row(self, row: int, plane: int) -> bytes:
        bpr = self.width // 8
        start = (row * 4 + plane) * bpr
        return self.planes[start:start + bpr]

    def build(self) -> bytes:
        return self.planes + self.mask


@dataclass(frozen=True)
class Hexunit:
    big: tuple
    small: tuple

    @classmethod
    def parse(cls, raw: bytes) -> "Hexunit":
        if len(raw) != FILE_SIZE:
            raise ValueError(f"expected {FILE_SIZE} bytes, got {len(raw)}")
        big = tuple(Sprite(40, 26, raw[o:o + 520], raw[o + 520:o + BIG_SIZE])
                    for o in range(0, BIG_COUNT * BIG_SIZE, BIG_SIZE))
        small = tuple(Sprite(24, 20, raw[o:o + 240], raw[o + 240:o + SMALL_SIZE])
                      for o in (SMALL_OFFSET, SMALL_OFFSET + SMALL_SIZE))
        return cls(big, small)

    def build(self) -> bytes:
        out = b"".join(s.build() for s in self.big + self.small)
        if len(out) != FILE_SIZE:
            raise ValueError("invalid sprite sizes")
        return out


def pixels(sprite: Sprite, row: int) -> list[int]:
    """4-bit colour per pixel; plane p gives colour bit p (inferred plane order)."""
    vals = [0] * sprite.width
    for p in range(4):
        chunk = sprite.plane_row(row, p)
        for x in range(sprite.width):
            if chunk[x // 8] & (0x80 >> (x % 8)):
                vals[x] |= 1 << p
    return vals


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=ROOT / "private/game-dos-working/hexunit.dat")
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts/experiments/HEXUNIT-59-20261103/hexunit.json")
    ns = ap.parse_args(argv)
    raw = ns.source.read_bytes()
    hx = Hexunit.parse(raw)
    assert hx.build() == raw
    data = dict(sha256=hashlib.sha256(raw).hexdigest(), big=len(hx.big), small=len(hx.small), round_trip_equal=True,
                nonzero_mask_bytes=[sum(map(bool, s.mask)) for s in hx.big + hx.small])
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(big=len(hx.big), small=len(hx.small), round_trip_equal=True)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
