"""Lossless SAVEDATA parser: 20 slot headers x 12 bytes, then 20 slots x 10109 bytes at 0xF0.

A slot is a snapshot of DGROUP DS:0x42..0x27BE (main.exe 3597:091e save, 16db:081c load). Before writing,
3597:04d2 replaces near pointers with record indexes (0xFFFF = null); 16db:00b4 restores them on load.
Header word +10 is the 16-bit byte sum of the slot with pointers restored (16db:07c6 checks it).
"""
from dataclasses import dataclass
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLOTS = 20
HEADER_SIZE = 12
SLOT_SIZE = 0x277D
DATA_START = SLOTS * HEADER_SIZE  # 0xF0
FILE_SIZE = DATA_START + SLOTS * SLOT_SIZE
DS_BASE = 0x42  # slot byte 0 is DS:0x42
EMPTY = 6  # header byte 0 of an unused slot

# (DS offset of a pointer word, target array base, target record size), per 3597:04d2 / 16db:00b4
def pointer_sites(slot):
    sites = []
    for i in range(2):  # 65-byte records at DS:0x21A: 3 pointers when the type byte at +0x3F is > 7
        if slot[0x21A + i * 0x41 + 0x3F - DS_BASE] > 7:
            sites += [(0x21A + i * 0x41 + 0x17 + j * 4, 0x1A7C, 0x44) for j in range(3)]
    sites += [(0x142 + i * 13, 0x1A7C, 0x44) for i in range(2)]
    sites += [(0x2052 + 2 * i, 0x1A7C, 0x44) for i in range(42)]
    sites += [(0x20A6 + 2 * i, 0x14FC, 0x16) for i in range(8)]
    for i in range(64):
        for j in range(2):
            r = 0x14FC + i * 0x16 + j * 4
            if slot[r + 0xE - DS_BASE] in (2, 9, 11, 12):
                sites.append((r + 0xC, 0x14FC, 0x16))
    sites += [(0x14FC + i * 0x16, 0x7FC, 13) for i in range(64)]
    sites += [(0x7FC + i * 13, 0x7FC, 13) for i in range(256)]
    return sites


def restore_pointers(slot):
    """Slot bytes as they are in memory after load (indexes -> near pointers)."""
    out = bytearray(slot)
    for ds, base, size in pointer_sites(slot):
        v = struct.unpack_from('<H', out, ds - DS_BASE)[0]
        struct.pack_into('<H', out, ds - DS_BASE, 0 if v == 0xFFFF else (base + v * size) & 0xFFFF)
    return bytes(out)


def checksum(slot):
    return sum(restore_pointers(slot)) & 0xFFFF


@dataclass(frozen=True)
class Header:
    raw: bytes

    @property
    def selector(self): return self.raw[0]       # DS:0x43, scedata record +1; 6 = empty slot
    @property
    def flag_4b(self): return self.raw[1]        # DS:0x4B
    @property
    def date(self): return tuple(self.raw[2:6])  # DS:0x44..0x47: year-1940, month, day, hour
    @property
    def words(self): return struct.unpack_from('<HH', self.raw, 6)  # DS:0x5E, DS:0x60
    @property
    def checksum(self): return struct.unpack_from('<H', self.raw, 10)[0]


@dataclass(frozen=True)
class Savedata:
    headers: tuple
    slots: tuple

    @classmethod
    def parse(cls, raw):
        if len(raw) != FILE_SIZE: raise ValueError(f'SAVEDATA must contain {FILE_SIZE} bytes')
        return cls(tuple(Header(raw[i * HEADER_SIZE:(i + 1) * HEADER_SIZE]) for i in range(SLOTS)),
                   tuple(raw[DATA_START + i * SLOT_SIZE:DATA_START + (i + 1) * SLOT_SIZE] for i in range(SLOTS)))

    def build(self):
        if len(self.headers) != SLOTS or len(self.slots) != SLOTS: raise ValueError('Need 20 headers and slots')
        if any(len(h.raw) != HEADER_SIZE for h in self.headers) or any(len(s) != SLOT_SIZE for s in self.slots):
            raise ValueError('Invalid header or slot size')
        return b''.join(h.raw for h in self.headers) + b''.join(self.slots)

    def checksum_ok(self, i):
        return self.headers[i].checksum == checksum(self.slots[i])

    def with_bytes(self, i, edits):
        """Copy with slot i bytes changed ({DS offset: byte}); header date/selector mirrored, checksum fixed."""
        slot = bytearray(self.slots[i])
        for ds, v in edits.items():
            slot[ds - DS_BASE] = v
        head = bytearray(self.headers[i].raw)
        head[0] = slot[0x43 - DS_BASE]
        head[1] = slot[0x4B - DS_BASE]
        head[2:6] = slot[0x44 - DS_BASE:0x48 - DS_BASE]
        head[6:10] = slot[0x5E - DS_BASE:0x62 - DS_BASE]
        struct.pack_into('<H', head, 10, checksum(bytes(slot)))
        hs, ss = list(self.headers), list(self.slots)
        hs[i], ss[i] = Header(bytes(head)), bytes(slot)
        return Savedata(tuple(hs), tuple(ss))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=ROOT / 'private/game-dos-working/SAVEDATA')
    a = ap.parse_args()
    raw = a.source.read_bytes()
    s = Savedata.parse(raw)
    used = [i for i in range(SLOTS) if s.headers[i].selector != EMPTY]
    print(json.dumps(dict(round_trip_equal=s.build() == raw, sha256=hashlib.sha256(raw).hexdigest(),
                          used_slots=[dict(slot=i, selector=s.headers[i].selector, date=s.headers[i].date,
                                           checksum_ok=s.checksum_ok(i)) for i in used])))
