"""TASK-008: read-only second seek/read audit; no inferred game semantics."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/experiments/TASK-008'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    binary = (ROOT / 'private/game-dos/main.exe').read_bytes()
    expected = '0b33be2fd37b965e5b92d1881f34226c1608eff6d0358787a7cb5049f218e9df'
    if sha(binary) != expected:
        raise ValueError('Unexpected binary')
    export = json.loads((ROOT / 'artifacts/experiments/TASK-007A/one-function.json').read_text(encoding='utf-8'))
    for ins in export['instructions']:
        pos, raw = int(ins['file_offset'], 16), bytes.fromhex(ins['bytes_hex'])
        if binary[pos:pos+len(raw)] != raw:
            raise ValueError(f'Export mismatch at {pos:#x}')
    # Name association uses an inferred on-disk segment origin, NOT measured DS.
    origin = 0x4FFAC - 0x2E8C
    name_offset = origin + 0x2EF2
    if binary[name_offset:name_offset+11] != b'MAPINF.DAT\0':
        raise ValueError('Candidate name bytes differ')
    cases = []
    for value in range(256):
        ax = 0
        ax = (ax & 0xFF00) | value
        ax &= 0x7F
        product = ax * 0x640
        dx, ax = (product >> 16) & 0xFFFF, product & 0xFFFF
        if ((dx << 16) | ax) != (value & 127) * 1600:
            raise ValueError('Arithmetic mismatch')
        cases.append({'source_byte': value, 'seek_offset': (dx << 16) | ax})
    profiles = []
    for name in ['mapinf.dat', 'mappno.dat', 'hexdisp.dat']:
        data = (ROOT / 'private/game-dos' / name).read_bytes()
        blocks = [data[i:i+1600] for i in range(0, len(data), 1600)]
        profiles.append({'file': name, 'sha256': sha(data), 'size': len(data),
                         'stride_candidate': 1600, 'remainder': len(data) % 1600,
                         'blocks': [{'file_offset': i*1600, 'size': len(b), 'sha256': sha(b),
                                     'distinct_bytes': len(set(b)), 'zero_count': b.count(0)}
                                    for i,b in enumerate(blocks)]})
    result = {
        'binary_sha256': expected, 'verified_instructions': len(export['instructions']),
        'candidate_name': {'file_offset': hex(name_offset), 'value': 'MAPINF.DAT',
                           'inferred_file_segment_origin': hex(origin),
                           'lea_file_offset': '0xD180', 'lea_ghidra': '16db:03d0',
                           'operand_offset': '0x2EF2', 'confidence': 'inferred'},
        'seek': {'call_file_offset': '0xD19F', 'call_ghidra': '16db:03ef',
                 'arithmetic_file_range': '0xD18C..0xD19B inclusive',
                 'origin_al': 0, 'offset': '(byte_at_runtime_DS_0043 & 127) * 1600',
                 'checked_source_byte_values': 256, 'max_offset': cases[-1]['seek_offset']},
        'read': {'call_file_offset': '0xD1B2', 'call_ghidra': '16db:0402',
                 'requested_count_cx': 1600, 'buffer_offset_dx': '0x20B6',
                 'handle': '[BP-2] from preceding open', 'ds': 'unknown', 'runtime_result': 'unknown'},
        'profiles': profiles,
        'limits': ['Runtime DS and opened file identity remain unknown.',
                   'Equal sizes of multiple files do not establish their roles or shared record semantics.',
                   'No successful seek or read was observed.',
                   'The source byte at DS:0043 cannot yet be equated to byte 1 of the preceding file read: an intervening helper call exists.',
                   '1600 bytes does not establish a 40 by 40 grid.']}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'measurement.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'candidate':result['candidate_name'],'seek':result['seek'], 'read':result['read'],
                      'file_sizes':{p['file']:p['size'] for p in profiles}}))


if __name__ == '__main__':
    main()
