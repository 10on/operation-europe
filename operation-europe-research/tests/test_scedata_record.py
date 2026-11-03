import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scedata_record as sr  # noqa: E402

GAME = ROOT / "private/game-dos-working/scedata"
EXPECTED_SHA = "a213bdfb541780259bdf789b514896fa4f1278c826f789206bbb0d17d1355936"


def synthetic(records=7):
    texts = b"".join(bytes([65 + n]) * 10 + b"\0" * 790 for n in range(12))
    body = b"".join(bytes([n, 0x80 | n]) + bytes(range(5)) + bytes([(n * 7 + k) & 255 for k in range(sr.RECORD_SIZE - 7)]) for n in range(records))
    return texts + body


class SyntheticTests(unittest.TestCase):
    def test_round_trip(self):
        raw = synthetic()
        parsed = sr.Scedata.parse(raw)
        self.assertEqual(parsed.build(), raw)
        self.assertEqual([r.map_index for r in parsed.records], list(range(7)))

    def test_malformed_framing(self):
        raw = synthetic()
        for bad in (raw[:-1], raw + b"\0", raw[: sr.HEADER_SIZE - 1]):
            with self.assertRaises(ValueError):
                sr.Scedata.parse(bad)

    def test_record_field_lengths(self):
        r = sr.Record.parse(synthetic(1)[sr.HEADER_SIZE:])
        with self.assertRaises(ValueError):
            sr.Record(r.tag, r.selector_raw, b"\0" * 4, r.opaque_tail).build()


@unittest.skipUnless(GAME.exists(), "working copy of scedata not present (private/, not in git)")
class GameFileTests(unittest.TestCase):
    def test_original_round_trip_sha(self):
        raw = GAME.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_SHA)
        built = sr.Scedata.parse(raw).build()
        self.assertEqual(hashlib.sha256(built).hexdigest(), EXPECTED_SHA)

    def test_masked_map_indices(self):
        parsed = sr.Scedata.parse(GAME.read_bytes())
        self.assertEqual([r.map_index for r in parsed.records], [0, 0, 1, 2, 3, 4, 5])


if __name__ == "__main__":
    unittest.main()
