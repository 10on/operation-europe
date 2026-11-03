"""Run the TASK-007A function in Unicorn (16-bit real mode) and compare it with a DOSBox-X trace.

Callees are stubbed with DOS semantics (open/seek/read/close); registers that only callees
set (BX, CX, DX after close and 1000:6e64) are excluded at the mapinf checkpoints.
Exit 0 ok, 1 mismatch, 2 bad input.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE
from unicorn.x86_const import *

ROOT = Path(__file__).resolve().parents[1]
REGS = dict(AX=UC_X86_REG_AX, BX=UC_X86_REG_BX, CX=UC_X86_REG_CX, DX=UC_X86_REG_DX, SP=UC_X86_REG_SP,
            DS=UC_X86_REG_DS, SS=UC_X86_REG_SS, CS=UC_X86_REG_CS, IP=UC_X86_REG_IP)
EXCLUDE = {0x3d0: {'BX', 'CX', 'DX'}, 0x3d9: {'CX'}}
STUBS = {0x977e: 'open', 0x009b: 'seek', 0x0043: 'read', 0x0032: 'close', 0x6e64: 'near6e64'}
BP0 = 0x1234


def compare_regs(emu, trace, exclude):
    cmp = {k: [emu[k], trace[k]] for k in REGS if k in trace and k not in exclude}
    return all(a == b for a, b in cmp.values()), cmp


def run(function, hits, files, al=1):
    ins = function['instructions']
    code = bytearray()
    for i in ins:  # apply MZ relocation to CALLF segment words, as the DOS loader does
        b = bytearray.fromhex(i['bytes_hex'])
        if b[0] == 0x9a:
            b[3:5] = struct.pack('<H', struct.unpack('<H', b[3:5])[0] + hits[0]['load_base'])
        code += b
    gseg, off0 = (int(x, 16) for x in ins[0]['ghidra'].split(':'))
    base = hits[0]['load_base']
    cs = gseg - 0x1000 + base
    lib = base  # Ghidra segment 0x1000 at runtime
    near6e64 = cs * 16 + (0x10000 + 0x6e64 - gseg * 16)
    addrs = [cs * 16 + int(i['ghidra'].split(':')[1], 16) for i in ins]
    mu = Uc(UC_ARCH_X86, UC_MODE_16)
    mu.mem_map(0, 0x110000 + 0xF000 & ~0xFFF)
    mu.mem_write(0, b'\xf4')
    mu.mem_write(addrs[0], bytes(code))
    h0 = hits[0]['registers']
    sp_entry = h0['SP'] + 10
    for r, v in dict(CS=cs, IP=off0, DS=h0['DS'], SS=h0['SS'], SP=sp_entry).items():
        mu.reg_write(REGS[r], v)
    for r, v in ((UC_X86_REG_ES, h0['DS']), (UC_X86_REG_BP, BP0), (UC_X86_REG_AX, al),
                 (UC_X86_REG_BX, h0['BX']), (UC_X86_REG_CX, 0x5555), (UC_X86_REG_DX, 0x6666)):
        mu.reg_write(r, v)
    ss, ds = h0['SS'], h0['DS']
    lin = lambda seg, o: (seg << 4) + (o & 0xFFFF)
    rw = lambda seg, o: struct.unpack('<H', mu.mem_read(lin(seg, o), 2))[0]
    mu.mem_write(lin(ss, sp_entry), struct.pack('<HH', 0, 0))  # far return to 0000:0000 (HLT)
    tags = {h['tag']: h for h in hits}
    for t in ('scedata', 'mapinf'):  # DGROUP file-name strings as dumped by the debugger at DS:DX
        mu.mem_write(lin(ds, tags[t + '-open']['registers']['DX']), bytes.fromhex(tags[t]['name_hex']))
    by_ip = {h['registers']['IP']: h for h in hits}
    st = dict(executed=[], checkpoints=[], seeks={}, buffers={}, handles={}, pos={}, next=9)

    def hook(uc, address, size, _):
        if address in addrs:
            st['executed'].append(address)
            ip = address - cs * 16
            if ip in by_ip:
                h = by_ip[ip]
                emu = {k: uc.reg_read(r) for k, r in REGS.items()}
                ok, cmp = compare_regs(emu, h['registers'], EXCLUDE.get(ip, set()))
                st['checkpoints'].append(dict(tag=h['tag'], ip=hex(ip), match=ok, excluded=sorted(EXCLUDE.get(ip, ())),
                                              compared={k: [hex(a), hex(b)] for k, (a, b) in cmp.items()}))
            return
        o = address - lib * 16
        if address == near6e64:  # PUSH CS; CALL near: Ghidra 1000:6e64 is linear, i.e. offset in this CS
            o = 0x6e64
        elif o not in STUBS or o == 0x6e64:
            return
        sp = uc.reg_read(UC_X86_REG_SP)
        arg = lambda n: rw(ss, sp + 4 + 2 * n)
        kind = STUBS[o]
        if kind == 'open':
            bx = uc.reg_read(UC_X86_REG_BX)
            name = bytes(uc.mem_read(lin(ds, bx), 16)).split(b'\0')[0].decode('latin1').upper()
            hnd = st['next']
            st['handles'][hnd] = name
            st['pos'][hnd] = 0
            uc.reg_write(UC_X86_REG_AX, hnd)
            uc.reg_write(UC_X86_REG_DX, bx)
        elif kind == 'seek':
            hnd, pos = arg(0), arg(1) | arg(2) << 16
            st['pos'][hnd] = pos
            st['seeks'][st['handles'][hnd]] = pos
            uc.reg_write(UC_X86_REG_AX, arg(1))
            uc.reg_write(UC_X86_REG_DX, arg(2))
        elif kind == 'read':
            hnd, buf, cnt = arg(0), arg(1), arg(2)
            name = st['handles'][hnd]
            data = files[name][st['pos'][hnd]:st['pos'][hnd] + cnt]
            uc.mem_write(lin(ds, buf), data)
            st['buffers'][name] = dict(buf=hex(buf), count=len(data), sha256=hashlib.sha256(data).hexdigest())
            for r, v in ((UC_X86_REG_AX, len(data)), (UC_X86_REG_BX, hnd), (UC_X86_REG_CX, cnt), (UC_X86_REG_DX, buf)):
                uc.reg_write(r, v)
        elif kind == 'close':
            uc.reg_write(UC_X86_REG_AX, 0)
        ip, rcs = rw(ss, sp), rw(ss, sp + 2)  # RETF
        uc.reg_write(UC_X86_REG_SP, sp + 4)
        uc.reg_write(UC_X86_REG_CS, rcs)
        uc.reg_write(UC_X86_REG_IP, ip)

    mu.hook_add(UC_HOOK_CODE, hook)
    for o in STUBS:  # each stub address holds a NOP so the hook fires before decoding junk
        mu.mem_write(lib * 16 + o, b'\x90')
    mu.emu_start(addrs[0], 0, count=1000)
    fin = dict(returned=mu.reg_read(UC_X86_REG_CS) == 0 and mu.reg_read(UC_X86_REG_IP) in (0, 1),
               sp_ok=mu.reg_read(UC_X86_REG_SP) == sp_entry + 4, bp_ok=mu.reg_read(UC_X86_REG_BP) == BP0,
               handle_slot=rw(ss, sp_entry - 4))
    return st, addrs, fin


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--function', type=Path, default=ROOT / 'artifacts/experiments/TASK-007A/one-function.json')
    ap.add_argument('--trace-run', type=Path, default=ROOT / 'artifacts/experiments/TRACE-49-20261103/run-20261103T012859Z')
    ap.add_argument('--scedata', type=Path, default=ROOT / 'private/game-dos-working/scedata')
    ap.add_argument('--mapinf', type=Path, default=ROOT / 'private/game-dos-working/mapinf.dat')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args(argv)
    if a.out and a.out.exists() and not a.force:
        print(f'refusing to overwrite {a.out}', file=sys.stderr)
        return 2
    try:
        function = json.loads(a.function.read_text(encoding='utf-8'))
        hits = json.loads((a.trace_run / 'hits.json').read_text(encoding='utf-8'))
        files = {'SCEDATA': a.scedata.read_bytes(), 'MAPINF.DAT': a.mapinf.read_bytes()}
    except (OSError, ValueError, KeyError) as e:
        print(f'bad input: {e}', file=sys.stderr)
        return 2
    st, addrs, fin = run(function, hits, files)
    expect = {h['tag'].split('-')[0].upper().replace('MAPINF', 'MAPINF.DAT'): h for h in hits if h['tag'].endswith('-read')}
    reads = {}
    for name, h in expect.items():
        mfo = (h.get('matching_file_offsets') or [None])[0]
        reads[name] = dict(seek_emu=st['seeks'].get(name), seek_trace=mfo,
                           sha_emu=st['buffers'].get(name, {}).get('sha256'), sha_trace=h.get('name_sha256'))
    reads_ok = all(r['seek_emu'] == r['seek_trace'] and (r['sha_trace'] is None or r['sha_emu'] == r['sha_trace']) for r in reads.values())
    in_order = st['executed'] == addrs
    ok = in_order and len(st['checkpoints']) == len(hits) and all(c['match'] for c in st['checkpoints']) \
        and reads_ok and fin['returned'] and fin['sp_ok'] and fin['bp_ok'] and fin['handle_slot'] == 9
    res = dict(instructions_executed=len(st['executed']), all_60_in_order=in_order, checkpoints=st['checkpoints'],
               reads=reads, final=fin, ok=ok)
    text = json.dumps(res, indent=2) + '\n'
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text, encoding='utf-8')
    print(json.dumps(dict(ok=ok, instructions_executed=len(st['executed']), all_60_in_order=in_order,
                          checkpoints_matched=sum(c['match'] for c in st['checkpoints']), reads_ok=reads_ok, final=fin)))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
