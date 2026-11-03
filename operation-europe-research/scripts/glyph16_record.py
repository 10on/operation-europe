"""Lossless parser for MSG / EMSG: 16x16 1bpp glyph banks (32 bytes per glyph, 2 bytes per row,
MSB = leftmost pixel). EMSG ends with a 24-byte partial glyph kept as raw tail.
Glyph shapes observed by rendering (kanji); how the game indexes them is unknown.
"""
from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLYPH = 32


@dataclass(frozen=True)
class GlyphBank:
    glyphs: tuple
    tail: bytes

    @classmethod
    def parse(cls, raw):
        n = len(raw) // GLYPH
        return cls(tuple(raw[i * GLYPH:(i + 1) * GLYPH] for i in range(n)), raw[n * GLYPH:])

    def pixels(self, i):
        g = self.glyphs[i]
        return [[(g[2 * y] << 8 | g[2 * y + 1]) >> (15 - x) & 1 for x in range(16)] for y in range(16)]

    def build(self):
        if any(len(g) != GLYPH for g in self.glyphs) or len(self.tail) >= GLYPH:
            raise ValueError('Invalid glyph framing')
        return b''.join(self.glyphs) + self.tail


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path, nargs='?', default=ROOT / 'private/game-dos-working/msg')
    raw = ap.parse_args().source.read_bytes()
    b = GlyphBank.parse(raw)
    print(json.dumps(dict(glyphs=len(b.glyphs), tail=len(b.tail), round_trip_equal=b.build() == raw,
                          sha256=hashlib.sha256(raw).hexdigest())))
