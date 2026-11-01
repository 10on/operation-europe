"""Check the file/image coordinate conversion on a synthetic MZ fixture."""

import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mz_inspect.py"
SPEC = importlib.util.spec_from_file_location("mz_inspect", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class TestMZInspect(unittest.TestCase):
    def test_entry_and_relocation_coordinates(self):
        header = bytearray(64)
        # One page, 80 bytes total, 64-byte header, 16-byte load image.
        struct.pack_into("<14H", header, 0, 0x5A4D, 80, 1, 1, 4,
                         2, 0xFFFF, 1, 0, 0, 3, 0, 30, 0)
        struct.pack_into("<HH", header, 30, 4, 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "fixture.exe"
            path.write_bytes(header + bytes(16))
            result = module.inspect(path)
        self.assertEqual(result["entry_image_offset"], 3)
        self.assertEqual(result["entry_file_offset"], 67)
        self.assertEqual(result["relocation_targets"]["count"], 1)
        self.assertEqual(result["relocation_targets"]["sample_first_and_last"][0]["target_file_offset"], 68)
        self.assertEqual(result["relocation_targets"]["outside_file_image_count"], 0)
        self.assertEqual(result["stack_image_offset"], 16)
        self.assertTrue(result["stack_within_file_image_plus_minalloc"])


if __name__ == "__main__":
    unittest.main()
