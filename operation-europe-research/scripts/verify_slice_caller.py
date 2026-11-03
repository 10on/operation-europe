"""Recover far-return caller from captured stack, check original call bytes.

Default: checks only, prints a one-line JSON verdict, writes nothing.
--write-report PATH: writes the report to PATH and caller.json into the run dir (refuses to overwrite unless --force).
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = 'verify_slice_caller'


def save(pairs, force):
    for path, _ in pairs:
        if path.exists() and not force:
            print(f'refusing to overwrite {path} (use --force)', file=sys.stderr)
            return 2
    for path, text in pairs:
        path.write_text(text, encoding='utf-8')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Recover far-return caller from captured stack and check CALL bytes. Writes nothing unless --write-report.')
    ap.add_argument('run', help='runtime capture directory')
    ap.add_argument('--write-report', metavar='PATH', help='write report JSON to PATH (also writes caller.json into run dir)')
    ap.add_argument('--force', action='store_true', help='overwrite existing output files')
    args = ap.parse_args(argv)
    run = Path(args.run).resolve()
    try:
        result=json.loads((run/'result.json').read_text())
        session=json.loads((run/'session.json').read_text())
        assert session['unchanged'] and not result['timed_out']
        hit=result['hits'][0];base=result['entry']['CS']
        stack=(run/'entry-stack.bin').read_bytes()
        ip,cs=struct.unpack_from('<HH',stack)
        return_image=(cs-base)*16+ip
        return_file=return_image+0x6000
        source=ROOT/'private/game-dos/main.exe';data=source.read_bytes()
        assert hashlib.sha256(data).hexdigest()==session['before']
        candidates=[]
        if data[return_file-3]==0xe8:
            displacement=struct.unpack_from('<h',data,return_file-2)[0]
            target_image=(cs-base)*16+((ip+displacement)&65535)
            if target_image==0x71c6 and data[return_file-4]==0x0e:
                candidates.append({'kind':'PUSH CS; near CALL','call_file_offset':hex(return_file-3),'push_cs_file_offset':hex(return_file-4),'target_image_offset':hex(target_image),'bytes_hex':data[return_file-4:return_file].hex()})
        if data[return_file-5]==0x9a:
            ti,ts=struct.unpack_from('<HH',data,return_file-4)
            if ts*16+ti==0x71c6:
                candidates.append({'kind':'CALL FAR (unrelocated target)','call_file_offset':hex(return_file-5),'target_image_offset':hex(ts*16+ti),'bytes_hex':data[return_file-5:return_file].hex()})
        assert len(candidates)==1, candidates
        measurement={'runtime_return':f'{cs:04x}:{ip:04x}','return_file_offset':hex(return_file),'load_base':hex(base),'verified_call':candidates[0],'entry_ax':hit['registers']['AX'],'entry_bx':hex(hit['registers']['BX']),'stack_address':f'{hit["registers"]["SS"]:04x}:{hit["registers"]["SP"]:04x}','source_sha256':hashlib.sha256(data).hexdigest()}
        cmp_text=json.dumps(measurement,indent=2)+'\n'
        evidence=[]
        for id,path in [('stack',run/'entry-stack.bin'),('result',run/'result.json'),('session',run/'session.json'),('caller',run/'caller.json'),('source',source)]:
            sha=hashlib.sha256(cmp_text.encode('utf-8')).hexdigest() if id=='caller' else hashlib.sha256(path.read_bytes()).hexdigest()
            evidence.append({'id':id,'path':str(path.relative_to(ROOT)),'kind':'local evidence','sha256':sha})
        report={'schema_version':'1','task_id':'TASK-019','status':'COMPLETED','goal':'Locate actual caller of 800-byte SCEDATA reader','methods':['Stop at function entry before prologue','Read 16 bytes SS:SP through native debugger','Decode far-return IP:CS; verify preceding CALL and target against original MZ bytes'],'environment':{'emulator':'DOSBox-X','main_sha256':session['before'],'load_base':hex(base)},'claims':[{'text':json.dumps(measurement),'confidence':'confirmed','evidence_ids':['stack','result','source','caller']}],'evidence':evidence,'human_summary_ru':'Найден вызывающий участок по runtime-стеку и независимо проверен по байтам CALL. Это один наблюдённый caller, не полный список.','open_questions':['Purpose of caller and downstream text renderer','Other callers and input values not enumerated'],'next_step':'Bounded Ghidra analysis around verified caller; trace caller buffer into display or parsing routine.'}
    except AssertionError as e:
        print(json.dumps({'ok': False, 'script': NAME, 'error': str(e) or repr(e)}))
        return 1
    pairs = []
    if args.write_report:
        pairs = [(run/'caller.json', cmp_text), (Path(args.write_report), json.dumps(report,ensure_ascii=False,indent=2)+'\n')]
    code = save(pairs, args.force)
    if code:
        return code
    verdict = {'ok': True, 'script': NAME, **measurement}
    if args.write_report:
        verdict['report'] = args.write_report
    print(json.dumps(verdict))
    return 0


if __name__ == '__main__':
    sys.exit(main())
