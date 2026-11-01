"""Verify TASK-008 bounded CFG bytes and its explicitly resolved jump table."""
import csv
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/experiments/TASK-008'
binary = (ROOT / 'private/game-dos/main.exe').read_bytes()
digest = hashlib.sha256(binary).hexdigest()
if digest != '0b33be2fd37b965e5b92d1881f34226c1608eff6d0358787a7cb5049f218e9df':
    raise ValueError('Unexpected binary')
rows = list(csv.DictReader((OUT / 'helper-flow.tsv').read_text(encoding='utf-8').splitlines(), delimiter='\t'))
instructions = [r for r in rows if r['kind'] == 'insn']
positions = set()
for row in instructions:
    offset = int(row['file_offset'], 16)
    raw = bytes.fromhex(row['bytes_or_target'])
    if offset in positions or binary[offset:offset+len(raw)] != raw:
        raise ValueError(f'Duplicate or byte mismatch: {offset:#x}')
    positions.add(offset)
table = struct.unpack_from('<8H', binary, 0xCED2)
if set(table) != {0xC4, 0xEE}:
    raise ValueError('Jump table no longer matches manually seeded targets')
summary = [r for r in rows if r['kind'] == 'summary']
if len(summary) != 1 or summary[0]['asm'] != 'queue_remaining=0;cancelled=false':
    raise ValueError('Incomplete traversal')
issues = [r for r in rows if r['kind'] in {'outside','missing'}]
if issues:
    raise ValueError('Missing or out-of-range targets')
result = {
    'binary_sha256': digest, 'instruction_count': len(instructions),
    'all_exported_bytes_match': True, 'unique_instruction_file_offsets': len(positions),
    'file_first_instruction': hex(min(positions)), 'file_last_instruction': hex(max(positions)),
    'traversal_queue_remaining': 0,
    'call_count': sum(r['kind'] == 'call' for r in rows),
    'computed_jumps': [r for r in rows if r['kind'] == 'computed'],
    'jump_table': {'file_offset':'0xCED2','entry_width_bytes':2,
                   'entries':[{'index':i,'cs_offset':hex(v),'file_target':hex(0xCDB0+v)} for i,v in enumerate(table)]},
    'explicit_ds_mentions': [r for r in instructions if 'DS' in r['asm']],
    'nonstack_mov_stores': [r for r in instructions if r['asm'].startswith('MOV ') and '[' in r['asm'].split(',')[0]
                           and '[BP ' not in r['asm'].split(',')[0]],
    'limits': ['Bounded static CFG with two manually resolved table targets; not runtime execution.',
               'Absence of explicit DS writes does not prove lack of DS:0043 aliasing through indexed memory or SS.',
               'No game meaning assigned to fields, counters or branch categories.']}
(OUT / 'helper-verified.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['instruction_count','unique_instruction_file_offsets','all_exported_bytes_match','call_count','explicit_ds_mentions']}))
