"""Синтетические проверки нормализации/хеша/сравнения трасс (без DOSBox)."""
import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('oe_trace_recheck', Path(__file__).resolve().parents[1] / 'scripts' / 'oe_trace_recheck.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def regs(cs, ip, ds, dx, ax):
    return {'CS': cs, 'IP': ip, 'DS': ds, 'DX': dx, 'AX': ax}


def sample():
    hits = []
    for tag, name, rd in [('scedata', b'SCEDATA\0', 8143), ('mapinf', b'MAPINF.DAT\0', 1600)]:
        hits += [{'tag': tag, 'registers': regs(0xF24, 0x394, 0x4F5B, 0x2E8C, 0), 'name_hex': (name + b'x' * 8).hex()},
                 {'tag': tag + '-open', 'registers': regs(0xF24, 0x39D, 0x4F5B, 0, 9)},
                 {'tag': tag + '-read', 'registers': regs(0xF24, 0x3BC, 0x4F5B, 0, rd)}]
    bufs = {t: {'sha256': 'ab' * 32, 'compare_ok': True} for t in ('scedata', 'mapinf')}
    return {'entry': {'CS': 0x849}}, hits, bufs


class TraceTest(unittest.TestCase):
    def test_normalize(self):
        t = m.normalize_trace(*sample())
        self.assertEqual(t['load_base'], '0x849')
        self.assertEqual(t['scedata']['bp_cs_ip'], '0F24:0394')
        self.assertEqual(t['scedata']['ds_dx_string'], 'SCEDATA')
        self.assertEqual(t['mapinf']['ds_dx_string'], 'MAPINF.DAT')
        self.assertEqual((t['scedata']['open_ax'], t['scedata']['read_ax']), (9, 8143))

    def test_hash_stable_and_order_free(self):
        t = m.normalize_trace(*sample())
        self.assertEqual(m.trace_hash(t), m.trace_hash(dict(reversed(list(t.items())))))
        self.assertEqual(len(m.trace_hash(t)), 64)

    def test_compare(self):
        a = m.normalize_trace(*sample())
        b = copy.deepcopy(a)
        self.assertTrue(m.compare({'o': a, 'r1': b})['all_equal'])
        b['mapinf']['buffer_sha256'] = 'cd' * 32
        c = m.compare({'o': a, 'r1': b})
        self.assertFalse(c['all_equal'])
        self.assertEqual([d['path'] for d in c['differences']['r1']], ['/mapinf/buffer_sha256'])


if __name__ == '__main__':
    unittest.main()
