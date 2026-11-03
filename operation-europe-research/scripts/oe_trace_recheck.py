"""Повтор динамической трассы TASK-010 (SCEDATA/MAPINF) и сравнение с оригиналом.

Команда: python -I scripts/oe_trace_recheck.py --runs 2 --experiment TRACE-49-20261103
На каждый запуск: dosboxx_probe_session.py --auto --autotype --new-console --experiment ID
(та же последовательность, что у оригинала: AUTOTYPE 'space enter enter enter', BP 0849:7144...),
затем verify_runtime_reads.py <run> (только проверка), затем нормализованная трасса.
Пишет artifacts/experiments/<ID>/comparison.json и report.json. Токены не используются.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = 'artifacts/experiments/TASK-010/run-20261030T010340Z'
TAGS = [('scedata', 17743, 8143), ('mapinf', 0, 1600)]
SOURCES = {'scedata': 'scedata', 'mapinf': 'mapinf.dat'}
RUN_TIMEOUT = 600


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalize_trace(result, hits, buffers):
    """Чистая функция. result: result.json; hits: hits.json (list); buffers: {tag: {'sha256','compare_ok'}}."""
    by_tag = {h['tag']: h for h in hits}
    trace = {'load_base': hex(result['entry']['CS'])}
    for tag, _, _ in TAGS:
        b, o, r = by_tag[tag], by_tag[tag + '-open'], by_tag[tag + '-read']
        regs = b['registers']
        name = bytes.fromhex(b['name_hex']).split(b'\0')[0].decode('ascii', 'replace')
        trace[tag] = {'bp_cs_ip': '%04X:%04X' % (regs['CS'], regs['IP']),
                      'ds': '%04X' % regs['DS'], 'dx': '%04X' % regs['DX'], 'ds_dx_string': name,
                      'open_ax': o['registers']['AX'], 'read_ax': r['registers']['AX'],
                      'buffer_compare_ok': bool(buffers[tag]['compare_ok']),
                      'buffer_sha256': buffers[tag]['sha256']}
    return trace


def trace_hash(trace):
    return sha(json.dumps(trace, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode())


def diff_traces(a, b, path=''):
    """Список различий (путь, значение a, значение b) двух нормализованных трасс."""
    out = []
    for k in sorted(set(a) | set(b)):
        p = path + '/' + k
        if k not in a or k not in b:
            out.append({'path': p, 'a': a.get(k), 'b': b.get(k)})
        elif isinstance(a[k], dict) and isinstance(b[k], dict):
            out += diff_traces(a[k], b[k], p)
        elif a[k] != b[k]:
            out.append({'path': p, 'a': a[k], 'b': b[k]})
    return out


def compare(traces):
    """traces: {имя: трасса}; сравнение каждой с первой."""
    names = list(traces)
    base = names[0]
    return {'baseline': base, 'hashes': {n: trace_hash(t) for n, t in traces.items()},
            'all_equal': len({trace_hash(t) for t in traces.values()}) == 1,
            'differences': {n: diff_traces(traces[base], traces[n]) for n in names[1:]}}


def extract(run):
    run = Path(run)
    result = json.loads((run / 'result.json').read_text())
    hits = json.loads((run / 'hits.json').read_text())
    buffers = {}
    for tag, start, size in TAGS:
        raw = (run / (tag + '-read-name.bin')).read_bytes()
        data = (ROOT / 'private/game-dos-working' / SOURCES[tag]).read_bytes()
        buffers[tag] = {'sha256': sha(raw), 'compare_ok': len(raw) == size and raw == data[start:start + size]}
    return normalize_trace(result, hits, buffers)


def minimize(pid):
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        cb = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def visit(hwnd, _):
            p = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid and u.IsWindowVisible(hwnd):
                u.ShowWindowAsync(hwnd, 6)
            return True
        u.EnumWindows(cb(visit), 0)
    except Exception:
        pass


def one_run(exp, timeout, do_min=False):
    cmd = [sys.executable, '-I', str(ROOT / 'scripts/dosboxx_probe_session.py'), '--auto', '--autotype', '--new-console', '--experiment', exp]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines, state = [], {}

    def reader():
        for line in proc.stdout:
            lines.append(line.rstrip())
            try:
                j = json.loads(line)
                if j.get('ready'):
                    state['pid'] = j['pid']
                if j.get('finished'):
                    state['evidence'] = j['evidence']
            except ValueError:
                pass
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    end = time.monotonic() + timeout
    while proc.poll() is None and time.monotonic() < end:
        if do_min and 'pid' in state:
            minimize(state['pid'])
        time.sleep(1)
    timed_out = proc.poll() is None
    if timed_out:
        if 'pid' in state:  # только процесс DOSBox-X, запущенный этим прогоном
            subprocess.run(['taskkill', '/PID', str(state['pid']), '/F'], capture_output=True)
        proc.kill()
    proc.wait(timeout=30)
    t.join(timeout=5)
    return {'exit': proc.returncode, 'timed_out': timed_out, 'dosbox_pid': state.get('pid'),
            'evidence': state.get('evidence'), 'tail': lines[-5:]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--runs', type=int, default=2)
    ap.add_argument('--experiment', required=True)
    ap.add_argument('--minimize', action='store_true', help='сворачивать окно DOSBox-X (в первой попытке привело к 0 hits)')
    ap.add_argument('--timeout', type=int, default=RUN_TIMEOUT)
    args = ap.parse_args(argv)
    exp_dir = ROOT / 'artifacts/experiments' / args.experiment
    traces, runs = {'original': extract(ROOT / ORIGINAL)}, []
    blocked = None
    for i in range(1, args.runs + 1):
        info = one_run(args.experiment, args.timeout, args.minimize)
        info['name'] = f'run{i}'
        runs.append(info)
        if info['timed_out'] or not info['evidence'] or info['exit'] != 0:
            blocked = f"run{i}: exit={info['exit']} timed_out={info['timed_out']} tail={info['tail']}"
            break
        run_dir = Path(info['evidence'])
        info['run_dir'] = str(run_dir.relative_to(ROOT)) if run_dir.is_absolute() else str(run_dir)
        v = subprocess.run([sys.executable, '-I', str(ROOT / 'scripts/verify_runtime_reads.py'), str(run_dir)], cwd=ROOT, capture_output=True, text=True)
        info['verify_exit'] = v.returncode
        info['verify_stdout'] = v.stdout.strip()[-300:]
        try:
            traces[info['name']] = extract(run_dir)
        except Exception as e:  # noqa: BLE001
            blocked = f'run{i}: extract failed: {e!r}'
            break
    exp_dir.mkdir(parents=True, exist_ok=True)
    cmp_ = compare(traces)
    comparison = {'experiment': args.experiment, 'command': f'python -I scripts/oe_trace_recheck.py --runs {args.runs} --experiment {args.experiment}',
                  'original_run': ORIGINAL, 'runs': runs, 'traces': traces, 'comparison': cmp_, 'blocked': blocked}
    (exp_dir / 'comparison.json').write_text(json.dumps(comparison, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    ok = blocked is None and all(r.get('verify_exit') == 0 for r in runs)
    evidence = [{'id': 'comparison', 'path': str((exp_dir / 'comparison.json').relative_to(ROOT)), 'kind': 'local comparison artifact',
                 'sha256': sha((exp_dir / 'comparison.json').read_bytes())}]
    claims = []
    if ok:
        for r in runs:
            d = Path(r['run_dir'])
            for f in ('hits.json', 'result.json', 'session.json'):
                evidence.append({'id': f"{r['name']}-{f.split('.')[0]}", 'path': str(d / f), 'kind': 'local runtime artifact', 'sha256': sha((ROOT / d / f).read_bytes())})
        eq = cmp_['all_equal']
        claims.append({'text': 'Хеши нормализованных трасс (load_base, BP CS:IP, DS, DX, строка DS:DX, AX open/read, сравнение и sha256 буфера) для оригинала и %d повторов: %s. Различия: %s.' % (
            len(runs), 'все равны' if eq else 'не все равны', json.dumps(cmp_['differences'], ensure_ascii=False)),
            'confidence': 'observed', 'evidence_ids': ['comparison']})
        claims.append({'text': 'verify_runtime_reads.py (только проверка) для повторов: коды выхода %s.' % [r['verify_exit'] for r in runs],
                       'confidence': 'observed', 'evidence_ids': ['comparison']})
    summary = ('Повтор трассы TASK-010 выполнен; ' + ('трассы совпали.' if ok and cmp_['all_equal'] else 'см. comparison.json.')) if ok else 'BLOCKED/FAILED: ' + str(blocked)
    report = {'schema_version': '1', 'task_id': args.experiment, 'status': 'COMPLETED' if ok else 'FAILED',
              'goal': 'Повторить динамическую трассу TASK-010 дважды одной командой и сравнить с оригиналом (hub #49)',
              'methods': ['scripts/dosboxx_probe_session.py --auto --autotype --new-console --experiment ID', 'verify_runtime_reads.py (check-only)', 'Нормализация трассы и sha256 канонического JSON'],
              'environment': {'emulator': 'DOSBox-X C:/DOSBox-X/dosbox-x.exe', 'load_base': traces.get('run1', traces['original'])['load_base']},
              'claims': claims, 'evidence': evidence, 'human_summary_ru': summary,
              'open_questions': ['Только один сценарий (первый); другие не проверены.'],
              'next_step': 'При расхождениях разобрать пути из comparison.json; иначе принять #11.'}
    (exp_dir / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'ok': ok, 'hashes': cmp_['hashes'], 'all_equal': cmp_['all_equal'], 'blocked': blocked}))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
