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

    def test_france_arrays_match_city_screen(self):
        france = sr.Scedata.parse(GAME.read_bytes()).records[1]
        self.assertEqual(france.city(0), dict(name=b"San Michel", fuel=20000, ammo=20000, food=50000, endurance=(50, 50)))
        self.assertEqual(france.city(2)["food"], 25000)
        self.assertEqual(sum(bool(c[0]) for c in france.array("cities")), 11)
        self.assertEqual(france.regiment(0x80), dict(next=0x81, type=119, strength=529))
        self.assertEqual(france.division(32)["first_regiment"], 0x80)
        # Division 32 = side 1, army 0, HQ: cell (22, 3), on-map and HQ bits set (DIVXY-223).
        d32 = france.division(32)
        self.assertEqual((d32["x"], d32["y"], d32["kind"] & 5), (22, 3, 5))


class ArrayLayoutTests(unittest.TestCase):
    def test_arrays_fit_record_without_overlap(self):
        spans = sorted((o, o + s * n) for o, s, n in sr.ARRAYS.values())
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])))
        self.assertLessEqual(spans[-1][1], sr.RECORD_SIZE)


if __name__ == "__main__":
    unittest.main()
