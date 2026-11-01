"""Bounded, sequential Jev experiment; no retries, no raw secret logging.

Budget authorization renewed by user on 2026-10-29, USD 1 total / USD 0.50
without demonstrated utility. This runner always enforces the lower USD 0.50.
Each request reserves USD 0.01 permanently, even on failure. At the documented
USD 0.042/M input tokens and default 64k context, this exceeds a full request.
Reservation is deliberately NOT released when usage is lower.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/experiments/JEV-001'
RATE = 0.042 / 1_000_000
# Renewed for today's work, without resetting any prior reservation or spend.
EXPIRES = dt.datetime.fromisoformat('2026-10-30T08:00:00+01:00')


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def check_budget(now, reserved_calls):
    if now >= EXPIRES:
        raise ValueError('Night authorization expired')
    if type(reserved_calls) is not int or not 0 <= reserved_calls < 50:
        raise ValueError('USD 0.50 reserved budget exhausted or invalid ledger')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Redirect refused')


def run(batch_path):
    check_budget(dt.datetime.now(dt.timezone.utc), 0)
    key = os.environ.get('TYPESAFE_API_KEY', '').strip()
    if not key:
        raise ValueError('Missing TYPESAFE_API_KEY')
    batch = json.loads(batch_path.read_text(encoding='utf-8'))
    payload = batch['request']
    if set(payload) != {'model', 'state', 'questions'} or payload['model'] != 'jev-1.14.0':
        raise ValueError('Only pinned text-only model request is supported')
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    if len(body) > 16000 or len(payload['questions']) > 16:
        raise ValueError('Bounded probe size exceeded')
    if batch['expected'] is not None and set(batch['expected']) != set(payload['questions']):
        raise ValueError('Missing expected answers')
    OUT.mkdir(parents=True, exist_ok=True)
    lock = OUT / 'budget.lock'
    # Exclusive creation prevents concurrent callers from overspending.
    with lock.open('x', encoding='utf-8') as f:
        f.write(str(os.getpid()))
    try:
        entries = sorted(OUT.glob('call-*.json'))
        check_budget(dt.datetime.now(dt.timezone.utc), len(entries))
        path = OUT / f'call-{len(entries)+1:03}.json'
        record = {'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                  'status': 'reserved', 'reserved_usd': 0.01,
                  'pricing_source': 'https://docs.typesafe.ai/models',
                  'input_usd_per_million': 0.042, 'output_usd_per_million': 0,
                  'request': payload, 'expected': batch['expected'],
                  'request_sha256': hashlib.sha256(body).hexdigest()}
        save(path, record)  # Durable reservation BEFORE sending anything.
        started = time.perf_counter()
        try:
            req = urllib.request.Request('https://api.typesafe.ai/v1/systemone',
                  data=body, headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as response:
                raw = response.read().decode('utf-8')
                # A server must never echo credentials into artifacts.
                raw = raw.replace(key, '[REDACTED]')
                record['response_body'] = raw
                record['http_status'] = response.status
            result = json.loads(raw)
            record['response'] = result
            answers = result['answers']
            if set(answers) != set(payload['questions']):
                raise ValueError('Answer keys differ from request')
            grade = {}
            for name, wanted in (batch['expected'] or {}).items():
                answer = answers[name]
                options = payload['questions'][name]['criteria']
                if answer.get('type') != 'choice' or answer.get('choice') not in options:
                    raise ValueError('Invalid choice answer')
                grade[name] = {'expected': wanted, 'actual': answer['choice'],
                               'correct': wanted == answer['choice']}
            tokens = result['usage']['input_tokens']
            if type(tokens) is not int or tokens < 0:
                raise ValueError('Invalid input token count')
            record.update(status='completed', grade=grade, estimated_cost_usd=tokens * RATE,
                          cost_note='Published token rate times reported usage; not account invoice')
        except Exception as e:
            record['status'] = 'error'
            record['error_type'] = type(e).__name__
            if isinstance(e, urllib.error.HTTPError):
                record['http_status'] = e.code
            # Do not log exception text/headers, which can contain credentials.
        finally:
            record['elapsed_ms'] = round((time.perf_counter() - started) * 1000)
            save(path, record)
        print(json.dumps({'log': str(path), 'status': record['status'],
                          'elapsed_ms': record['elapsed_ms'],
                          'estimated_cost_usd': record.get('estimated_cost_usd'),
                          'reserved_total_usd': (len(entries) + 1) / 100,
                          'correct': sum(g['correct'] for g in record.get('grade', {}).values()),
                          'total': len(batch['expected'] or {}), 'unlabeled': batch['expected'] is None}))
        return 0 if record['status'] == 'completed' else 1
    finally:
        lock.unlink()


if __name__ == '__main__':
    raise SystemExit(run(Path(sys.argv[1])))
