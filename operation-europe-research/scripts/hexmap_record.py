"""Lossless HEXMAP.DAT parser: 537 blocks of 196 bytes = 14x14 cells.

Code at Ghidra 3a96:0106..0173 (file ~0x30A5x..0x30AC3): seek ((word DS:B4AA[selector&127]) + v - 1) * 196,
read 196 bytes to DS:CF00, then for 14x14 bytes keeps bits 6-7 and replaces bits 0-5 via 3000:aa24.
v is a byte from a per-cell map (source not yet identified; mappno.dat is a candidate).
Scenario block bases from DS:B4AA: 0, 93, 181, 242, 327, 448.
"""
from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK = 196
SIDE = 14
SCENARIO_BASE = (0, 93, 181, 242, 327, 448)


@dataclass(frozen=True)
class Hexmap:
    blocks: tuple

    @classmethod
    def parse(cls, raw):
        if not raw or len(raw) % BLOCK: raise ValueError('Invalid HEXMAP framing')
        return cls(tuple(raw[n:n + BLOCK] for n in range(0, len(raw), BLOCK)))

    def cell(self, block, x, y):
        b = self.blocks[block][y * SIDE + x]
        return b & 0x3F, b >> 6

    def scenario_blocks(self, scenario):
        end = SCENARIO_BASE[scenario + 1] if scenario + 1 < len(SCENARIO_BASE) else len(self.blocks)
        return self.blocks[SCENARIO_BASE[scenario]:end]

    def build(self):
        if any(len(b) != BLOCK for b in self.blocks): raise ValueError('Invalid block size')
        return b''.join(self.blocks)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=ROOT / 'private/game-dos-working/hexmap.dat')
    raw = ap.parse_args().source.read_bytes()
    h = Hexmap.parse(raw)
    print(json.dumps(dict(blocks=len(h.blocks), per_scenario=[len(h.scenario_blocks(i)) for i in range(6)],
                          round_trip_equal=h.build() == raw, sha256=hashlib.sha256(raw).hexdigest())))
