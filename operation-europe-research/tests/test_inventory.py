import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("inventory", ROOT / "scripts" / "inventory.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class TestInventory(unittest.TestCase):
    def test_non_mz(self):
        self.assertIsNone(module.analyze_mz(b"hello", 5))

    def test_mz(self):
        import struct
        header = bytearray(64)
        struct.pack_into("<14H", header, 0, 0x5A4D, 64, 2, 0, 4, 0, 0xffff, 0, 0x100, 0, 0x100, 0, 0x1c, 0)
        obj = module.analyze_mz(bytes(header), 576)
        self.assertEqual(obj["declared_file_bytes"], 576)
        self.assertEqual(obj["initial_cs_ip"], "0000:0100")

    def test_inventory_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            game.mkdir()
            (game / "TEXT.DAT").write_bytes(b"HELLO WORLD\x00MORE DATA\x00")
            result = root / "artifacts" / "inventory.json"
            cp = subprocess.run([sys.executable, str(ROOT / "scripts" / "inventory.py"), str(game), "--out", str(result)], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertTrue(result.exists())
            import json
            data = json.loads(result.read_text())
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["files"][0]["magic"], "not_identified")


if __name__ == "__main__":
    unittest.main()
