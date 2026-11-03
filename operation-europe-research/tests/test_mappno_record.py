import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mappno_record as mp  # noqa: E402

GAME = ROOT / "private/game-dos-working/mappno.dat"
EXPECTED_SHA = "12c45df5e8dd8c64b6047cd72b1f75c399adc39b0ec610ebaa6272b3d81cc3e9"


class SyntheticTests(unittest.TestCase):
    def test_round_trip(self):
        raw = bytes(n % 80 for n in range(mp.REGION_SIZE * 6))
        self.assertEqual(mp.Mappno.parse(raw).build(), raw)


@unittest.skipUnless(GAME.exists(), "working copy of mappno.dat not present (private/, not in git)")
class GameFileTests(unittest.TestCase):
    def test_original_round_trip_sha(self):
        raw = GAME.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_SHA)
        m = mp.Mappno.parse(raw)
        self.assertEqual(len(m.regions), 6)
        self.assertEqual(hashlib.sha256(m.build()).hexdigest(), EXPECTED_SHA)
        self.assertLess(max(raw), 80)


if __name__ == "__main__":
    unittest.main()
