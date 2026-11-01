"""Check that wrong or malformed model outputs cannot pass the smoke-test gate."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("probe", Path(__file__).resolve().parents[1] / "scripts/local_model_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class GradeTest(unittest.TestCase):
    def test_gate(self):
        cases = json.dumps([{"id": "result", "options": ["8143", "unknown"]}])
        expected = json.dumps({"result": "unknown"})
        for answer, code in [('{"result":"unknown"}', 0), ('{"result":"8143"}', 1),
                             ('{"result":8143}', 1), ('{"result":"unknown","extra":1}', 1),
                             ('{}', 1), ('[]', 1), ('```json\n{}\n```', 1)]:
            with patch.object(Path, "read_text", side_effect=[cases, expected]), \
                 patch.object(Path, "read_bytes", return_value=answer.encode()), \
                 patch.object(probe, "save"):
                self.assertEqual(probe.grade(Path("answer.json")), code)


if __name__ == "__main__":
    unittest.main()
