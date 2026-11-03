import hashlib
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import koei_pic as kp  # noqa: E402

GAME = ROOT / "private/game-dos-working"
EXPECTED = {  # name: (sha256, picture sectors, tail bytes)
    "scesel.dat": ("e2b054989074", [0, 29, 44, 51, 65, 76, 91], 1024),
    "event.dat": ("4dc686d01325", None, 0),
    "sceend.dat": ("3b4aa8290406", [0, 3, 8, 12, 17, 22, 27, 80, 147, 217], 0),
}


def picture(w, h, table):
    # One copy command (0x8F = 16 cells) repeated per row, enough for w <= 64.
    head = struct.pack("<HH", w, h) + (bytes(16) if table else b"")
    return head + bytes([0x8F]) * h


class SyntheticTests(unittest.TestCase):
    def test_stream_length_modes(self):
        self.assertEqual(kp.stream_length(picture(64, 3, False), 0, False), 4 + 3)
        self.assertEqual(kp.stream_length(picture(64, 3, True), 0, True), 20 + 3)
        # literals: no table -> 2 bytes; table: 0x38 class -> 3 bytes, table entry -> 1 byte
        self.assertEqual(kp.stream_length(struct.pack("<HH", 4, 1) + b"\x00\x11", 0, False), 6)
        self.assertEqual(kp.stream_length(struct.pack("<HH", 4, 1) + bytes(16) + b"\x38\x01\x02", 0, True), 23)
        self.assertEqual(kp.stream_length(struct.pack("<HH", 4, 1) + bytes(16) + b"\x40", 0, True), 21)

    def test_sector_file_round_trip(self):
        a, b = picture(64, 3, False), picture(32, 2, False)
        raw = a + b"\xAA" * (512 - len(a)) + b + bytes(512 - len(b)) + bytes(512)
        f = kp.SectorFile.parse(raw, False)
        self.assertEqual([s for s, _ in f.pictures], [0, 1])
        self.assertEqual(len(f.tail), 512)
        self.assertEqual(f.build(), raw)

    def test_malformed(self):
        with self.assertRaises(ValueError):
            kp.stream_length(picture(64, 3, False)[:-1], 0, False)
        with self.assertRaises(ValueError):
            kp.stream_length(struct.pack("<HH", 641, 1) + b"\x80", 0, False)


@unittest.skipUnless((GAME / "scesel.dat").exists(), "working copy not present (private/, not in git)")
class GameFileTests(unittest.TestCase):
    def test_round_trip_and_sectors(self):
        for name, (sha, sectors, tail) in EXPECTED.items():
            raw = (GAME / name).read_bytes()
            self.assertTrue(hashlib.sha256(raw).hexdigest().startswith(sha), name)
            f = kp.SectorFile.parse(raw, kp.FILES[name])
            self.assertEqual(f.build(), raw, name)
            self.assertEqual(len(f.tail), tail, name)
            if sectors:
                self.assertEqual([s for s, _ in f.pictures], sectors, name)
        event = kp.SectorFile.parse((GAME / "event.dat").read_bytes(), False)
        self.assertEqual(len(event.pictures), 33)
        self.assertIn(231, [s for s, _ in event.pictures])  # sector 0xE7 used by 2707:03e4


if __name__ == "__main__":
    unittest.main()
