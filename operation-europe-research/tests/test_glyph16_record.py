import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import glyph16_record as g  # noqa: E402

GAME = ROOT / "private/game-dos-working"
FILES = {"msg": ("10939b59eb96abbe6c91df543369a5fe18e3b35df25c24417551c9ffe76ea274", 945, 0),
         "emsg": ("baee2b5f05782e7705b2adb945916a65dc48b623eaa899a3541820db87d3813f", 190, 24)}


class SyntheticTests(unittest.TestCase):
    def test_round_trip_and_pixels(self):
        raw = bytes([0x80, 0x01] + [0] * 30) + b"\xff" * 5
        b = g.GlyphBank.parse(raw)
        self.assertEqual(b.build(), raw)
        self.assertEqual(len(b.tail), 5)
        px = b.pixels(0)
        self.assertEqual((px[0][0], px[0][15], px[0][1], px[1][0]), (1, 1, 0, 0))


@unittest.skipUnless((GAME / "msg").exists(), "working copy not present (private/, not in git)")
class GameFileTests(unittest.TestCase):
    def test_original_round_trip_sha(self):
        for name, (sha, glyphs, tail) in FILES.items():
            raw = (GAME / name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), sha, name)
            b = g.GlyphBank.parse(raw)
            self.assertEqual((len(b.glyphs), len(b.tail)), (glyphs, tail), name)
            self.assertEqual(hashlib.sha256(b.build()).hexdigest(), sha, name)


if __name__ == "__main__":
    unittest.main()
