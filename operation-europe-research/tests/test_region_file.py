import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import region_file as rf  # noqa: E402

GAME = ROOT / "private/game-dos-working"
SHA = {"bigmap.dat": "f41d95c5af0e6f255087e7254ed91e4f4de6b586d2fc2843ca71342101f70b08",
       "midmap.dat": "45301d0ffe04676ee25f3f134af89dea2aca6a8eb1de0d47e32c19a7f7afbd0d",
       "hexdisp.dat": "3b2b5df5c16ffc946df0d5af3dbec4cbe3b82cd36895706afa7b12857bf2a3f5"}


class SyntheticTests(unittest.TestCase):
    def test_round_trip_and_framing(self):
        raw = bytes(range(256)) * 12
        self.assertEqual(rf.build(rf.parse(raw, 3072), 3072), raw)
        with self.assertRaises(ValueError):
            rf.parse(raw[:-1], 3072)


@unittest.skipUnless((GAME / "bigmap.dat").exists(), "working copy not present (private/, not in git)")
class GameFileTests(unittest.TestCase):
    def test_original_round_trip_sha(self):
        for name, sha in SHA.items():
            raw = (GAME / name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), sha, name)
            regs = rf.parse(raw, rf.REGION_SIZES[name])
            self.assertEqual(len(regs), 6, name)
            self.assertEqual(hashlib.sha256(rf.build(regs, rf.REGION_SIZES[name])).hexdigest(), sha, name)


if __name__ == "__main__":
    unittest.main()
