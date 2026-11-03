"""Check scripts/oe_reloc_check.py on synthetic inputs only (run via subprocess)."""

import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "oe_reloc_check.py"


def run_check(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args],
                          capture_output=True, text=True, encoding="utf-8")


def build_mz(path: Path) -> bytes:
    """Tiny MZ: 64-byte header, CS:IP = 0000:0000, 2 relocations, entry 'mov di,4712h'."""
    body = bytearray(128)
    body[0:3] = b"\xBF\x12\x47"              # entry: mov di,4712h
    struct.pack_into("<H", body, 16, 0x4712)  # relocation 0 target (file 80): matches
    struct.pack_into("<H", body, 32, 0x0000)  # relocation 1 target (file 96): no match
    header = bytearray(64)
    struct.pack_into("<14H", header, 0, 0x5A4D, 128, 1, 2, 4,
                     0, 0xFFFF, 0, 0x100, 0, 0, 0, 28, 0)
    struct.pack_into("<HH", header, 28, 0x10, 0)
    struct.pack_into("<HH", header, 32, 0x20, 0)
    data = bytes(header + body)
    path.write_bytes(data)
    return data


class TestOEReloCheck(unittest.TestCase):
    def write_json(self, directory: str, payload) -> Path:
        path = Path(directory) / "extract.json"
        path.write_text(payload if isinstance(payload, str) else json.dumps(payload),
                        encoding="utf-8")
        return path

    def test_json_three_matches_among_five(self):
        words = [0x4712, 0x1234, 0x4712, 0x0000, 0x4712]
        relocs = [{"seg": 0, "off": i * 2, "word": w} for i, w in enumerate(words)]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(tmp, {"header_paragraphs": 4, "relocations": relocs})
            proc = run_check("--json", str(path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["input"], "json")
        self.assertEqual(result["relocation_count"], 5)
        self.assertEqual(result["match_count"], 3)
        self.assertEqual(result["verdict"], "found")
        self.assertEqual(result["match_file_offsets"], ["0x40", "0x44", "0x48"])
        self.assertIsNone(result["entry"])

    def test_json_no_matches(self):
        relocs = [{"seg": 1, "off": 0, "word": 0x1111}, {"seg": 0, "off": 8, "word": 0x2222}]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(tmp, {"header_paragraphs": 0, "relocations": relocs})
            proc = run_check("--json", str(path), "--value", "0x4712")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["match_count"], 0)
        self.assertEqual(result["verdict"], "not_found")
        self.assertEqual(result["value"], "0x4712")

    def test_json_empty_relocations_is_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(tmp, {"header_paragraphs": 2, "relocations": []})
            proc = run_check("--json", str(path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["relocation_count"], 0)
        self.assertEqual(result["verdict"], "no_data")

    def test_malformed_json_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(tmp, "{not json")
            proc = run_check("--json", str(path))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("malformed JSON", proc.stderr)

    def test_missing_key_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(tmp, {"relocations": []})
            proc = run_check("--json", str(path))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("header_paragraphs", proc.stderr)

    def test_exe_found_with_entry_di(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.exe"
            build_mz(path)
            proc = run_check("--exe", str(path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["input"], "exe")
        self.assertEqual(len(result["sha256"]), 64)
        self.assertEqual(result["relocation_count"], 2)
        self.assertEqual(result["match_count"], 1)
        self.assertEqual(result["match_file_offsets"], ["0x50"])
        self.assertEqual(result["verdict"], "found")
        self.assertEqual(result["entry"]["file_offset"], 64)
        self.assertEqual(result["entry"]["hits"], [{"reg": "di", "file_offset": 64}])
        self.assertFalse(result["entry"]["mov_ds_ax_within_16_bytes_after_ax_hit"])

    def test_exe_sha256_mismatch_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.exe"
            build_mz(path)
            proc = run_check("--exe", str(path), "--sha256", "0" * 64)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("sha256 mismatch", proc.stderr)


if __name__ == "__main__":
    unittest.main()
