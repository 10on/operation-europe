"""TASK-009: enumerate reviewed helper store formulas; conditional static result.

Not an x86 emulator or a proof against arbitrary SS/DS aliasing. The formulas
come from manual review of the byte-verified CFG and bounded loop counters.
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/experiments/TASK-009'


def main():
    data = (ROOT / 'private/game-dos/main.exe').read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != '0b33be2fd37b965e5b92d1881f34226c1608eff6d0358787a7cb5049f218e9df':
        raise ValueError('Unexpected binary')
    src = ROOT / 'artifacts/experiments/TASK-008/helper-flow.tsv'
    instructions = [r for r in csv.DictReader(src.read_text(encoding='utf-8').splitlines(), delimiter='\t') if r['kind']=='insn']
    for r in instructions:
        off=int(r['file_offset'],16); raw=bytes.fromhex(r['bytes_or_target'])
        if data[off:off+len(raw)] != raw:
            raise ValueError('Export mismatch')
    formulas = [
        (0xCE9A, '0x21A + 65*i + 0x3D; i=0..1', [0x21A+65*i+0x3D for i in range(2)]),
        (0xCEF9, '0x21A + 65*i + 4*j + 0x17; i=0..1,j=0..2', [0x21A+65*i+4*j+0x17 for i in range(2) for j in range(3)]),
        (0xCF5F, '0x142 + 13*i; i=0..1', [0x142+13*i for i in range(2)]),
        (0xCFB2, '0x2052 + 2*i; i=0..41; optional entry_AX != 0 path', [0x2052+2*i for i in range(42)]),
        (0xCFF4, '0x20A6 + 2*i; i=0..7; optional entry_AX != 0 path', [0x20A6+2*i for i in range(8)]),
        (0xD043, '0x14FC + 22*i + 4*j + 0x0C; i=0..63,j=0..1; conditional tag path', [0x14FC+22*i+4*j+12 for i in range(64) for j in range(2)]),
        (0xD0AB, '0x14FC + 22*i; i=0..63', [0x14FC+22*i for i in range(64)]),
        (0xD0F3, '0x7FC + 13*i; i=0..255', [0x7FC+13*i for i in range(256)])]
    stores=[r for r in instructions if r['asm'].startswith('MOV ') and '[' in r['asm'].split(',')[0] and '[BP ' not in r['asm'].split(',')[0]]
    if {int(r['file_offset'],16) for r in stores} != {p for p,_,_ in formulas}:
        raise ValueError('Reviewed formulas do not cover exported nonstack MOV stores')
    results=[]
    for off,expr,starts in formulas:
        touched={p+d for p in starts for d in (0,1)}
        if any(p<0 or p>65535 for p in touched):
            raise ValueError('Address wrapping requires separate analysis')
        results.append({'store_file_offset':hex(off),'formula':expr,'word_start_count':len(starts),
                        'first_byte':hex(min(touched)),'last_byte':hex(max(touched)),
                        'touches_DS_0043':0x43 in touched,'word_starts':starts})
    # Candidate input read starts at runtime DS:0042. Header byte at +1 maps to
    # scedata block +1 ONLY IF filename, DS, read success, and alias assumptions hold.
    scenario=(ROOT/'private/game-dos/scedata').read_bytes()
    candidates=[{'candidate_block_index':i,'file_offset':9600+i*8143+1,
                 'byte':scenario[9600+i*8143+1], 'masked_index':scenario[9600+i*8143+1]&127}
                for i in range((len(scenario)-9600)//8143)]
    result={'binary_sha256':sha,'export_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
            'store_formulas':results,'any_DS_store_hits_0043':any(r['touches_DS_0043'] for r in results),
            'scope':'Reviewed loop bounds with normal separate stack/code/data storage; enumerated superset including optional paths. Not full machine-state proof.',
            'assumptions':['No SS stack writes alias DS data or code.','Runtime code and jump table match the checked binary.','Loop locals are not externally modified.'],
            'candidate_scedata_byte1':candidates,'scedata_sha256':hashlib.sha256(scenario).hexdigest(),
            'remaining_unknowns':['Actual opened filename and runtime DS','Success and byte count of preceding read','SS/DS physical aliasing','Which candidate blocks correspond to real selected scenarios']}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'measurement.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'store_sites':len(results),'any_DS_store_hits_0043':result['any_DS_store_hits_0043'],'candidate_scedata_byte1':candidates}))


if __name__=='__main__':
    main()
