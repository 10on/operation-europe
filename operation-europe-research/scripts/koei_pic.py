"""Koei 16-colour picture stream (decoder 1000:30a6 in main.exe) and sector-aligned picture files.

Only framing is decoded here: header, optional colour table and the command stream length.
Pixel decoding is left for the graphics milestone. See docs/PICTURE_FILES_FORMAT.md.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTOR = 512
# File -> colour-table flag. The 1a04:01ce path (1000:3490) reads the table, 1a04:01a0 (1000:34a4) does not.
FILES = {'scesel.dat': True, 'event.dat': False, 'sceend.dat': False}


def _u16(data: bytes, off: int) -> int:
    if off < 0 or off + 2 > len(data):
        raise ValueError("truncated")
    return struct.unpack_from("<H", data, off)[0]


def stream_length(data: bytes, offset: int, table: bool) -> int:
    """Bytes one picture occupies at offset: header, table, then h rows of commands."""
    w = _u16(data, offset)
    h = _u16(data, offset + 2)
    if not (1 <= w <= 640 and 1 <= h <= 400):
        raise ValueError("invalid header")
    pos = offset + 4 + (16 if table else 0)
    cells_per_row = (w + 3) >> 2
    for _ in range(h):
        remaining = cells_per_row
        while remaining > 0:
            if pos >= len(data):
                raise ValueError("truncated")
            b = data[pos]
            pos += 1
            if b >= 0x80:  # copy from the left (bit 6 = 0) or from rows above (bit 6 = 1)
                count, extra = (b & 0x0F) + 1, 0
            elif not table:  # literal 1000:3320: 12-bit pattern from low nibble + next byte
                count, extra = ((b >> 4) & 7) + 1, 1
            else:  # literal 1000:334e: zero / table entry / 2-byte pattern / 1-byte pattern
                count = (b & 7) + 1
                t = b & 0x78
                extra = 0 if t == 0 or t & 0x40 else 2 if t == 0x38 else 1
            if pos + extra > len(data):
                raise ValueError("truncated")
            pos += extra
            remaining -= count
    return pos - offset


@dataclass(frozen=True)
class Picture:
    width: int
    height: int
    table: tuple | None
    stream: bytes

    @classmethod
    def parse(cls, data: bytes, offset: int, table: bool) -> "Picture":
        n = stream_length(data, offset, table)
        pos = offset + 4
        tbl = None
        if table:
            tbl = struct.unpack_from("<8H", data, pos)
            pos += 16
        return cls(_u16(data, offset), _u16(data, offset + 2), tbl, data[pos:offset + n])

    def build(self) -> bytes:
        out = struct.pack("<HH", self.width, self.height)
        if self.table is not None:
            out += struct.pack("<8H", *self.table)
        return out + self.stream


@dataclass(frozen=True)
class SectorFile:
    """Pictures each starting at a 512-byte sector; the game seeks to sector*512 (1a04:016c)."""
    pictures: tuple
    pads: tuple
    size: int
    tail: bytes = b''  # sectors after the last picture that do not start with a valid header

    @classmethod
    def parse(cls, data: bytes, table: bool) -> "SectorFile":
        pics, pads, off = [], [], 0
        while off < len(data):
            w, h = _u16(data, off), _u16(data, off + 2)
            if pics and not (1 <= w <= 640 and 1 <= h <= 400):
                return cls(tuple(pics), tuple(pads), len(data), data[off:])
            pic = Picture.parse(data, off, table)
            end = off + len(pic.build())
            nxt = -(-end // SECTOR) * SECTOR
            if nxt > len(data):
                raise ValueError("truncated")
            pics.append((off // SECTOR, pic))
            pads.append(data[end:nxt])
            off = nxt
        return cls(tuple(pics), tuple(pads), len(data))

    def build(self) -> bytes:
        out = bytearray()
        for (sector, pic), pad in zip(self.pictures, self.pads, strict=True):
            if sector * SECTOR != len(out):
                raise ValueError("invalid sector")
            out += pic.build() + pad
            if len(out) % SECTOR:
                raise ValueError("invalid padding")
        out += self.tail
        if len(out) != self.size:
            raise ValueError("invalid size")
        return bytes(out)


def verify(game: Path, out: Path):
    result = {}
    for name, table in FILES.items():
        raw = (game / name).read_bytes()
        f = SectorFile.parse(raw, table)
        assert f.build() == raw
        result[name] = dict(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw), round_trip_equal=True,
            tail_bytes=len(f.tail),
            pictures=[dict(sector=s, width=p.width, height=p.height, bytes=len(p.build()),
                           pad_nonzero=any(pad)) for (s, p), pad in zip(f.pictures, f.pads)])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: len(v['pictures']) for k, v in result.items()}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--game', type=Path, default=ROOT / 'private/game-dos-working')
    ap.add_argument('--out', type=Path, default=ROOT / 'artifacts/experiments/PICFILES-20261103/pictures.json')
    a = ap.parse_args()
    verify(a.game, a.out)
