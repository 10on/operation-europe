"""Validate the oe-facts schema and the main.exe seed against it."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "facts.schema.json"
SEED_PATH = ROOT / "facts" / "main_exe.facts.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestFactsSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load(SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)
        cls.seed = load(SEED_PATH)

    def assertValid(self, doc):
        errors = sorted(self.validator.iter_errors(doc), key=lambda e: list(e.path))
        self.assertEqual([], [e.message for e in errors])

    def assertInvalid(self, doc):
        self.assertTrue(list(self.validator.iter_errors(doc)), "document was accepted but must be rejected")

    def test_seed_validates(self):
        self.assertValid(self.seed)

    def test_extra_bytes_field_in_function_is_rejected(self):
        doc = copy.deepcopy(self.seed)
        doc["functions"][0]["bytes"] = "55 8b ec"
        self.assertInvalid(doc)

    def test_extra_disasm_field_in_top_level_is_rejected(self):
        doc = copy.deepcopy(self.seed)
        doc["disasm"] = []
        self.assertInvalid(doc)

    def test_bad_sha256_is_rejected(self):
        doc = copy.deepcopy(self.seed)
        doc["binary"]["sha256"] = doc["binary"]["sha256"][:-1] + "G"
        self.assertInvalid(doc)

        doc = copy.deepcopy(self.seed)
        doc["binary"]["sha256"] = doc["binary"]["sha256"].upper()
        self.assertInvalid(doc)

    def test_status_outside_enum_is_rejected(self):
        doc = copy.deepcopy(self.seed)
        doc["functions"][0]["status"] = "likely"
        self.assertInvalid(doc)

    def test_ghidra_address_must_be_segment_offset(self):
        doc = copy.deepcopy(self.seed)
        doc["functions"][0]["start"][1]["value"] = "0x16DB0378"
        self.assertInvalid(doc)

    def test_file_offset_must_be_hex(self):
        doc = copy.deepcopy(self.seed)
        doc["functions"][0]["start"][0]["value"] = "53544"
        self.assertInvalid(doc)

    def test_function_start_requires_at_least_one_address(self):
        doc = copy.deepcopy(self.seed)
        doc["functions"][0]["start"] = []
        self.assertInvalid(doc)

    def test_sources_require_at_least_one_entry(self):
        doc = copy.deepcopy(self.seed)
        doc["segments"][0]["sources"] = []
        self.assertInvalid(doc)

    def test_source_path_must_be_repo_relative(self):
        doc = copy.deepcopy(self.seed)
        doc["segments"][0]["sources"][0]["path"] = "C:/Users/x/report.json"
        self.assertInvalid(doc)


if __name__ == "__main__":
    unittest.main()
