"""No-clobber behaviour of scripts/verify_*.py (default run writes nothing; --write-report guarded by --force)."""
import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / 'scripts'
NAMES = ['helper_flow', 'helper_runtime', 'runtime_reads', 'scenario_slice', 'slice_caller', 'text_chain', 'text_consumer']


def load(name, root):
    spec = importlib.util.spec_from_file_location(f'verify_{name}', SCRIPTS / f'verify_{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = Path(root).resolve()
    return mod


def run_main(mod, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mod.main(argv)
    return code, out.getvalue(), err.getvalue()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot(root):
    return {str(p.relative_to(root)): sha(p) for p in Path(root).rglob('*') if p.is_file()}


def build_runtime_reads(root):
    scedata = bytes((i * 7 + 3) % 256 for i in range(17743 + 8143))
    mapinf = bytes((i * 11 + 5) % 256 for i in range(1600))
    src = root / 'private/game-dos-working'
    src.mkdir(parents=True)
    (src / 'scedata').write_bytes(scedata)
    (src / 'mapinf.dat').write_bytes(mapinf)
    run = root / 'artifacts/experiments/TASK-010/run1'
    run.mkdir(parents=True)
    (run / 'scedata-read-name.bin').write_bytes(scedata[17743:17743 + 8143])
    (run / 'mapinf-read-name.bin').write_bytes(mapinf)
    hits = [
        {'tag': 'scedata-open', 'registers': {'AX': 9}},
        {'tag': 'scedata', 'name_hex': b'SCEDATA\0'.hex(), 'registers': {}},
        {'tag': 'scedata-read', 'registers': {'AX': 8143, 'DS': 0x2000}, 'source_sha256': hashlib.sha256(scedata).hexdigest()},
        {'tag': 'mapinf-open', 'registers': {'AX': 9}},
        {'tag': 'mapinf', 'name_hex': b'MAPINF.DAT\0'.hex(), 'registers': {}},
        {'tag': 'mapinf-read', 'registers': {'AX': 1600, 'DS': 0x3000}, 'source_sha256': hashlib.sha256(mapinf).hexdigest()},
    ]
    (run / 'hits.json').write_text(json.dumps(hits))
    (run / 'result.json').write_text(json.dumps({'timed_out': False, 'entry': {'CS': 0x1000}, 'hits': hits}))
    (run / 'session.json').write_text(json.dumps({'unchanged': True, 'before': '0' * 64}))
    (run / 'commands.json').write_text('[]')
    (run / 'config.conf').write_text('[autoexec]\n')
    return run


def build_scenario_slice(root):
    data = bytes((i * 5 + 1) % 256 for i in range(8143))
    src = root / 'private/game-dos-working'
    src.mkdir(parents=True)
    (src / 'scedata').write_bytes(data)
    static = root / 'artifacts/experiments/JEV-003'
    static.mkdir(parents=True)
    (static / 'functions.tsv').write_text('x\n')
    run = root / 'artifacts/experiments/TASK-011/run1'
    run.mkdir(parents=True)
    (run / 'slice-read-name.bin').write_bytes(data[800:1600])
    (run / 'slice-name-name.bin').write_bytes(b'SCEDATA\0')
    hits = [
        {'tag': 'slice-entry', 'registers': {'AX': 2, 'BX': 0x1234, 'DS': 0x2000, 'SS': 0x2000}},
        {'tag': 'slice-seek', 'registers': {'AX': 800, 'DX': 0}},
        {'tag': 'slice-read', 'registers': {'AX': 800, 'DX': 0x1234}},
        {'tag': 'slice-open', 'registers': {'AX': 9}},
    ]
    (run / 'result.json').write_text(json.dumps({'timed_out': False, 'entry': {'CS': 0x1000}, 'hits': hits}))
    (run / 'session.json').write_text(json.dumps({'unchanged': True, 'before': '0' * 64}))
    (run / 'commands.json').write_text('[]')
    return run


class _Base:
    builder = None
    name = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.run = self.builder(self.root)
        self.exp = self.run.parent
        self.report = self.exp / 'report.json'
        self.report.write_bytes(b'PRE-EXISTING REPORT\n')
        self.mod = load(self.name, self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_run_writes_nothing(self):
        before = snapshot(self.root)
        code, out, _ = run_main(self.mod, [str(self.run)])
        self.assertEqual(code, 0)
        verdict = json.loads(out)
        self.assertTrue(verdict['ok'])
        self.assertEqual(verdict['script'], f'verify_{self.name}')
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(sha(self.report), hashlib.sha256(b'PRE-EXISTING REPORT\n').hexdigest())

    def test_write_report_new_path_creates_file(self):
        target = self.root / 'out' / 'new-report.json'
        target.parent.mkdir()
        code, _, _ = run_main(self.mod, [str(self.run), '--write-report', str(target)])
        self.assertEqual(code, 0)
        self.assertTrue(target.exists())
        self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['task_id'], self.exp.name)
        self.assertEqual(self.report.read_bytes(), b'PRE-EXISTING REPORT\n')

    def test_write_report_existing_path_refused_then_forced(self):
        target = self.root / 'existing.json'
        target.write_bytes(b'OLD CONTENT')
        digest = sha(target)
        code, _, err = run_main(self.mod, [str(self.run), '--write-report', str(target)])
        self.assertEqual(code, 2)
        self.assertIn('refusing', err)
        self.assertEqual(sha(target), digest)
        code, _, _ = run_main(self.mod, [str(self.run), '--write-report', str(target), '--force'])
        self.assertEqual(code, 0)
        self.assertNotEqual(sha(target), digest)
        self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['task_id'], self.exp.name)


class RuntimeReadsNoClobber(_Base, unittest.TestCase):
    builder = staticmethod(build_runtime_reads)
    name = 'runtime_reads'


class ScenarioSliceNoClobber(_Base, unittest.TestCase):
    builder = staticmethod(build_scenario_slice)
    name = 'scenario_slice'

    def test_failed_check_exits_1_with_ok_false(self):
        (self.run / 'slice-read-name.bin').write_bytes(b'\0' * 800)
        code, out, _ = run_main(self.mod, [str(self.run)])
        self.assertEqual(code, 1)
        verdict = json.loads(out)
        self.assertFalse(verdict['ok'])
        self.assertEqual(verdict['script'], 'verify_scenario_slice')


class HelpTests(unittest.TestCase):
    def test_help_mentions_write_report_and_force_for_all_seven(self):
        for name in NAMES:
            with self.subTest(script=name):
                p = subprocess.run([sys.executable, '-I', str(SCRIPTS / f'verify_{name}.py'), '--help'],
                                   capture_output=True, timeout=120)
                out = p.stdout.decode('utf-8', 'replace')
                self.assertEqual(p.returncode, 0, p.stderr.decode('utf-8', 'replace'))
                self.assertIn('--write-report', out)
                self.assertIn('--force', out)


if __name__ == '__main__':
    unittest.main()
