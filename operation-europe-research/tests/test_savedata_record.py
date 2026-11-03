import hashlib
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import savedata_record as sr  # noqa: E402

SAVE = ROOT / "artifacts/experiments/SAVE-222-20261103/save-a-5.10.40.bin"
EXPECTED_SHA = "7998a5ea974e4031c7a99a150acccc957dca1234bd883e4f0149e3de33119beb"


def synthetic():
    slot = bytearray(sr.SLOT_SIZE)
    slot[0x7FC + 13 - sr.DS_BASE:0x7FC + 15 - sr.DS_BASE] = struct.pack('<H', 0xFFFF)  # null pointer
    slot[0x7FC - sr.DS_BASE:0x7FE - sr.DS_BASE] = struct.pack('<H', 2)  # index 2 -> 0x7FC + 26
    head = bytes(10) + struct.pack('<H', sr.checksum(bytes(slot)))
    empty = bytes([sr.EMPTY]) + bytes(11)
    return head + empty * 19 + bytes(slot) * 20


class SyntheticTests(unittest.TestCase):
    def test_round_trip_and_checksum(self):
        raw = synthetic()
        s = sr.Savedata.parse(raw)
        self.assertEqual(s.build(), raw)
        self.assertTrue(s.checksum_ok(0))
        mem = sr.restore_pointers(s.slots[0])
        self.assertEqual(struct.unpack_from('<H', mem, 0x7FC - sr.DS_BASE)[0], 0x7FC + 26)
        self.assertEqual(struct.unpack_from('<H', mem, 0x7FC + 13 - sr.DS_BASE)[0], 0)

    def test_edit_fixes_checksum_and_header(self):
        s = sr.Savedata.parse(synthetic()).with_bytes(0, {0x46: 12, 0x47: 6})
        self.assertTrue(s.checksum_ok(0))
        self.assertEqual(s.headers[0].date[2:], (12, 6))

    def test_malformed(self):
        for bad in (b"", bytes(sr.FILE_SIZE - 1), bytes(sr.FILE_SIZE + 1)):
            with self.assertRaises(ValueError):
                sr.Savedata.parse(bad)


@unittest.skipUnless(SAVE.exists(), "locally produced save not present (artifacts/, not in git)")
class GameSaveTests(unittest.TestCase):
    def test_local_save_round_trip_and_checksum(self):
        raw = SAVE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), EXPECTED_SHA)
        s = sr.Savedata.parse(raw)
        self.assertEqual(hashlib.sha256(s.build()).hexdigest(), EXPECTED_SHA)
        self.assertTrue(s.checksum_ok(0))
        self.assertEqual(s.headers[0].date, (0, 5, 10, 0))
        self.assertEqual([h.selector for h in s.headers].count(sr.EMPTY), 19)


if __name__ == "__main__":
    unittest.main()
