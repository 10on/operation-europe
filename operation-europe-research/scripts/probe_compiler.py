"""Read-only compiler evidence, with file coordinates and explicit negative scans."""
import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/experiments/COMPILER-20261101'

def main():
    result = {}
    for name in ('main.exe', 'open.exe'):
        data = (ROOT / 'private/game-dos-working' / name).read_bytes()
        assert data == (ROOT / 'private/game-dos' / name).read_bytes(), name
        h = struct.unpack_from('<14H', data)
        header = h[4]*16
        entry = header + h[11]*16 + h[10]
        strings = []
        for m in re.finditer(rb'[\x20-\x7e]{5,}', data):
            if re.search(rb'borland|turbo c|turbo pascal|MS Run-Time|R600[0-9]|watcom|runtime error|run-time error|LZEXE|PKLITE|EXEPACK', m[0], re.I):
                strings.append({'file_offset':hex(m.start()), 'text':m[0].decode('ascii')})
        markers = {}
        for marker in (b'LZ90', b'LZ91', b'LZEXE', b'PKLITE', b'EXEPACK', b'Packed file is corrupt', b'Borland', b'Turbo C', b'WATCOM', b'Turbo Pascal'):
            markers[marker.decode()] = [hex(m.start()) for m in re.finditer(re.escape(marker), data)]
        reloc = [struct.unpack_from('<HH',data,h[12]+i*4) for i in range(h[3])]
        # Ghidra's existing imports use synthetic load segment 0x1000.
        listing = OUT / (name[:-4]+'-startup.tsv')
        checks = []
        if listing.exists():
            relocated = bytearray(data)
            for off,seg in reloc:
                p=header+seg*16+off
                struct.pack_into('<H',relocated,p,(struct.unpack_from('<H',data,p)[0]+0x1000)&65535)
            for line in listing.read_text(encoding='utf-8').splitlines()[1:]:
                parts=line.split('\t')
                if len(parts)!=4: raise ValueError(line)
                addr,offset,raw,asm=parts
                p=int(offset,16); expected=bytes.fromhex(raw)
                assert relocated[p:p+len(expected)]==expected,(name,addr)
                checks.append({'ghidra':addr,'file_offset':offset,'asm':asm})
        result[name] = {'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'header_bytes':header,
            'relocation_count':h[3], 'relocation_table_file_offset':hex(h[12]),
            'entry_mz_cs_ip':f'{h[11]:04x}:{h[10]:04x}','entry_file_offset':hex(entry),
            'entry_prefix_hex':data[entry:entry+16].hex(),'markers':markers,'runtime_strings':strings,
            'startup_instruction_count_verified':len(checks),
            'startup_selected':[c for c in checks if any(x in c['asm'] for x in ('DS','ES','CALL','RETF','SS','STOS','MOVSB'))]}
    OUT.mkdir(exist_ok=True)
    (OUT/'measurement.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({n:{'sha256':v['sha256'],'relocations':v['relocation_count'],'strings':len(v['runtime_strings']),'verified_instructions':v['startup_instruction_count_verified']} for n,v in result.items()}))

if __name__=='__main__': main()
