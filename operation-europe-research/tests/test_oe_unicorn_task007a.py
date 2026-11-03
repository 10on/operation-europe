import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import oe_unicorn_task007a as u  # noqa: E402

FUNC = ROOT / "artifacts/experiments/TASK-007A/one-function.json"
RUNS = sorted((ROOT / "artifacts/experiments/TRACE-49-20261103").glob("run-*"))
GAME = ROOT / "private/game-dos-working"


class CompareTests(unittest.TestCase):
    def test_equal_and_excluded(self):
        ok, cmp = u.compare_regs({"AX": 1, "BX": 2}, {"AX": 1, "BX": 3}, {"BX"})
        self.assertTrue(ok)
        self.assertEqual(cmp, {"AX": [1, 1]})

    def test_difference(self):
        ok, _ = u.compare_regs({"AX": 1}, {"AX": 2}, set())
        self.assertFalse(ok)


@unittest.skipUnless(FUNC.exists() and RUNS and (GAME / "scedata").exists(), "local artifacts/private data not present")
class TraceTests(unittest.TestCase):
    def test_matches_both_runs(self):
        for run in RUNS:
            self.assertEqual(u.main(["--trace-run", str(run)]), 0, run.name)

    def test_any_difference_fails(self):
        with tempfile.TemporaryDirectory() as d:
            hits = json.loads((RUNS[0] / "hits.json").read_text(encoding="utf-8"))
            hits[2]["registers"]["DX"] ^= 1
            (Path(d) / "hits.json").write_text(json.dumps(hits), encoding="utf-8")
            self.assertEqual(u.main(["--trace-run", d]), 1)

    def test_buffer_difference_fails(self):
        with tempfile.TemporaryDirectory() as d:
            mod = Path(d) / "scedata"
            shutil.copy(GAME / "scedata", mod)
            data = bytearray(mod.read_bytes())
            data[17743 + 100] ^= 0xFF
            mod.write_bytes(data)
            self.assertEqual(u.main(["--scedata", str(mod)]), 1)


if __name__ == "__main__":
    unittest.main()
