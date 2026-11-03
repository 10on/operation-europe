"""Чистые части scripts/oe_ghidra_from_facts.py: SHA до вызова Ghidra, схема, адреса."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("oe_gff", ROOT / "scripts" / "oe_ghidra_from_facts.py")
gff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gff)

FACTS = json.loads((ROOT / "facts" / "main_exe.facts.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "schemas" / "facts.schema.json").read_text(encoding="utf-8"))


class TestShaBeforeGhidra(unittest.TestCase):
    def test_sha_mismatch_aborts_without_subprocess(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / "main.exe"
            exe.write_bytes(b"not the game")
            facts = Path(d) / "facts.json"
            facts.write_text(json.dumps(FACTS), encoding="utf-8")
            proj = Path(d) / "proj"
            with mock.patch.object(gff.subprocess, "run") as run:
                rc = gff.main(["--facts", str(facts), "--exe", str(exe), "--project-dir", str(proj),
                               "--check-out", str(Path(d) / "check.json")])
            self.assertEqual(2, rc)
            run.assert_not_called()
            self.assertFalse(proj.exists())

    def test_check_sha_ok(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / "x"
            exe.write_bytes(b"abc")
            gff.check_sha(exe, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
            with self.assertRaises(gff.FactsError):
                gff.check_sha(exe, "0" * 64)


class TestValidation(unittest.TestCase):
    def test_seed_valid(self):
        gff.validate_facts(FACTS, SCHEMA)

    def test_unknown_field_rejected(self):
        bad = copy.deepcopy(FACTS)
        bad["functions"][0]["bytes"] = "90"
        with self.assertRaises(gff.FactsError):
            gff.validate_facts(bad, SCHEMA)


class TestAddresses(unittest.TestCase):
    def test_parse(self):
        self.assertEqual((0x16DB, 0x378), gff.parse_ghidra("16db:0378"))
        for bad in ("0xD128", "16db0378", "zz:01", "16db:03789"):
            with self.assertRaises(gff.FactsError):
                gff.parse_ghidra(bad)

    def test_function_entry_requires_ghidra_kind(self):
        with self.assertRaises(gff.FactsError):
            gff.pick_ghidra([{"kind": "file_offset", "value": "0xD128"}], "f")
        with self.assertRaises(gff.FactsError):
            gff.pick_ghidra([{"kind": "runtime", "value": "0849:0100"}], "f")
        self.assertEqual("16db:0378", gff.pick_ghidra(
            [{"kind": "file_offset", "value": "0xD128"}, {"kind": "ghidra", "value": "16DB:0378"}], "f"))

    def test_plan_rejects_inconsistent_file_offset(self):
        bad = copy.deepcopy(FACTS)
        bad["functions"][0]["start"][0]["value"] = "0xD129"
        with self.assertRaises(gff.FactsError):
            gff.build_plan(bad)

    def test_plan_dgroup_labels(self):
        rows, _ = gff.build_plan(FACTS)
        by_id = {r.split("\t")[1]: r.split("\t") for r in rows}
        self.assertEqual("5712:2e8c", by_id["DL_SCEDATA_NAME"][3])  # 0x1000 + 0x4712
        self.assertEqual("1000:0043", by_id["F_DOS_READ_WRAPPER"][3])
        self.assertEqual("MAPINF_DAT", by_id["DL_MAPINF_NAME"][2])

    def test_compare_with_ref(self):
        ref = {"instruction_count": 2, "instructions": [
            {"ghidra": "16db:0378", "bytes_hex": "55", "asm": "PUSH BP"},
            {"ghidra": "16db:0379", "bytes_hex": "8bec", "asm": "MOV BP,SP"}]}
        ok = [("16db:0378", 1, "PUSH"), ("16db:0379", 2, "MOV")]
        self.assertEqual([], gff.compare_with_ref(ok, ref))
        self.assertTrue(gff.compare_with_ref([ok[0], ("16db:0379", 2, "XOR")], ref))
        self.assertTrue(gff.compare_with_ref(ok[:1], ref))


if __name__ == "__main__":
    unittest.main()
