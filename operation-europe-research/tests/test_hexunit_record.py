import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import hexunit_record as hr  # noqa: E402

GAME = ROOT / "private/game-dos-working/hexunit.dat"
EXPECTED_PREFIX = "71a10bc66f6f"


class SyntheticTests(unittest.TestCase):
    def test_round_trip_and_layout(self):
        raw = bytes(n * 7 & 255 for n in range(hr.FILE_SIZE))
        hx = hr.Hexunit.parse(raw)
        self.assertEqual((len(hx.big), len(hx.small)), (52, 2))
        self.assertEqual(hx.build(), raw)
        self.assertEqual(hx.big[1].plane_row(1, 2), raw[650 + 20 + 10:650 + 20 + 15])
        self.assertEqual(hx.small[1].mask, raw[34100 + 240:34400])

    def test_pixels(self):
        planes = bytes([0x80, 0, 0, 0, 0, 0x80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x80, 0, 0, 0, 0]) + bytes(500)
        s = hr.Sprite(40, 26, planes, bytes(130))
        self.assertEqual(hr.pixels(s, 0)[:2], [0b1011, 0])

    def test_wrong_size(self):
        for n in (0, hr.FILE_SIZE - 1, hr.FILE_SIZE + 1):
            with self.assertRaises(ValueError):
                hr.Hexunit.parse(bytes(n))


@unittest.skipUnless(GAME.exists(), "working copy not present (private/, not in git)")
class GameFileTests(unittest.TestCase):
    def test_round_trip_and_mask_outlines_sprite(self):
        raw = GAME.read_bytes()
        self.assertTrue(hashlib.sha256(raw).hexdigest().startswith(EXPECTED_PREFIX))
        hx = hr.Hexunit.parse(raw)
        self.assertEqual(hx.build(), raw)
        # Mask bit 1 = background: coloured pixels almost never fall under a set mask bit.
        coloured = under_mask = 0
        for s in hx.big + hx.small:
            bpr = s.width // 8
            for r in range(s.height):
                for x, v in enumerate(hr.pixels(s, r)):
                    if v:
                        coloured += 1
                        under_mask += bool(s.mask[r * bpr + x // 8] & (0x80 >> (x % 8)))
        self.assertLess(under_mask / coloured, 0.05)


if __name__ == "__main__":
    unittest.main()
