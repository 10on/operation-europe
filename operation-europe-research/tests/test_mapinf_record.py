import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mapinf_record as mr  # noqa: E402

GAME = ROOT / "private/game-dos-working/mapinf.dat"
EXPECTED_SHA = "4c727005dbd92bddf526ad3c26823d799b112fc3a4f4e5ea69c551d3b932279f"


class SyntheticTests(unittest.TestCase):
    def test_round_trip_and_cells(self):
        raw = bytes((n * 7) & 0xFF for n in range(mr.REGION_SIZE * 2))
        m = mr.Mapinf.parse(raw)
        self.assertEqual(m.build(), raw)
        self.assertEqual(len(m.regions[0].rows), 40)
        b = raw[mr.REGION_SIZE + 3 * 40 + 5]
        self.assertEqual(m.regions[1].cell(5, 3), (b & 0x7F, bool(b & 0x80)))

    def test_malformed(self):
        for bad in (b"", b"\0" * 1599, b"\0" * 1601):
            with self.assertRaises(ValueError):
                mr.Mapinf.parse(bad)


@unittest.skipUnless(GAME.exists(), "working copy of mapinf.dat not present (private/, not in git)")
class GameFileTests(unittest.TestCase):
    def test_original_round_trip_sha(self):
        raw = GAME.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_SHA)
        m = mr.Mapinf.parse(raw)
        self.assertEqual(len(m.regions), 6)
        self.assertEqual(hashlib.sha256(m.build()).hexdigest(), EXPECTED_SHA)


if __name__ == "__main__":
    unittest.main()
