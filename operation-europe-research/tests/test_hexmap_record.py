import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import hexmap_record as hm  # noqa: E402

GAME = ROOT / "private/game-dos-working/hexmap.dat"
EXPECTED_SHA = "1d518aa602b2536650abd970298922e97b90ffbc3c70ed4dd53a71d7b2e8e67b"


class SyntheticTests(unittest.TestCase):
    def test_round_trip_and_cell(self):
        raw = bytes((n * 13) & 0xFF for n in range(hm.BLOCK * 3))
        h = hm.Hexmap.parse(raw)
        self.assertEqual(h.build(), raw)
        b = raw[hm.BLOCK + 2 * 14 + 3]
        self.assertEqual(h.cell(1, 3, 2), (b & 0x3F, b >> 6))
        with self.assertRaises(ValueError):
            hm.Hexmap.parse(raw[:-1])


@unittest.skipUnless(GAME.exists(), "working copy not present (private/, not in git)")
class GameFileTests(unittest.TestCase):
    def test_original_round_trip_sha(self):
        raw = GAME.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_SHA)
        h = hm.Hexmap.parse(raw)
        self.assertEqual(len(h.blocks), 537)
        self.assertEqual([len(h.scenario_blocks(i)) for i in range(6)], [93, 88, 61, 85, 121, 89])
        self.assertEqual(hashlib.sha256(h.build()).hexdigest(), EXPECTED_SHA)


if __name__ == "__main__":
    unittest.main()
