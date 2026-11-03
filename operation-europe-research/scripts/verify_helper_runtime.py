"""Compare scenario buffers around close/helper interval, preserving scope limits.

Default: checks only, prints a one-line JSON verdict, writes nothing.
--write-report PATH: writes the report to PATH and comparison.json into the run dir (refuses to overwrite unless --force).
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = 'verify_helper_runtime'


def save(pairs, force):
    for path, _ in pairs:
        if path.exists() and not force:
            print(f'refusing to overwrite {path} (use --force)', file=sys.stderr)
            return 2
    for path, text in pairs:
        path.write_text(text, encoding='utf-8')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Compare scenario buffers around close/helper interval. Writes nothing unless --write-report.')
    ap.add_argument('run', help='runtime capture directory')
    ap.add_argument('--write-report', metavar='PATH', help='write report JSON to PATH (also writes comparison.json into run dir)')
    ap.add_argument('--force', action='store_true', help='overwrite existing output files')
    args = ap.parse_args(argv)
    run = Path(args.run).resolve()
    try:
        result=json.loads((run/'result.json').read_text())
        session=json.loads((run/'session.json').read_text())
        assert not result['timed_out'] and session['unchanged']
        hits={h['tag']:h for h in result['hits']}
        before=(run/'helper-before-name.bin').read_bytes()
        after=(run/'helper-after-name.bin').read_bytes()
        assert len(before)==len(after)==8143
        assert hits['helper-before']['registers']['DS']==hits['helper-after']['registers']['DS']
        source=ROOT/'private/game-dos-working/scedata'
        data=source.read_bytes()
        matches=[n for n in range(9600,len(data)-8143+1,8143) if data[n:n+8143]==before]
        assert matches
        diff=[{'ds_offset':hex(i+0x42),'before':a,'after':b} for i,(a,b) in enumerate(zip(before,after)) if a!=b]
        static=ROOT/'artifacts/experiments/TASK-009/measurement.json'
        footprint=json.loads(static.read_text())
        allowed={start+delta for site in footprint['store_formulas'] for start in site['word_starts'] for delta in (0,1)}
        outside=[r for r in diff if int(r['ds_offset'],16) not in allowed]
        measurement={'source_matches':matches,'ds_0043_before':before[1],'ds_0043_after':after[1],'changed_byte_count':len(diff),'changed_bytes':diff,'outside_static_superset':outside,'scope':'One runtime interval after SCEDATA read until MAPINF LEA; includes DOS close and helper. Not a universal preservation proof; only 8143-byte buffer sampled.'}
        cmp_text=json.dumps(measurement,indent=2)+'\n'
        evidence=[]
        for id,path in [('result',run/'result.json'),('session',run/'session.json'),('before',run/'helper-before-name.bin'),('after',run/'helper-after-name.bin'),('comparison',run/'comparison.json'),('static',static),('source',source)]:
            sha=hashlib.sha256(cmp_text.encode('utf-8')).hexdigest() if id=='comparison' else hashlib.sha256(path.read_bytes()).hexdigest()
            evidence.append({'id':id,'path':str(path.relative_to(ROOT)),'kind':'local evidence','sha256':sha})
        report={'schema_version':'1','task_id':run.parent.name,'status':'COMPLETED','goal':'Measure DS:0043 and scenario buffer across close/helper interval','methods':['Two native debugger breakpoints image 716c and 7180','Full 8143-byte local buffer comparison','Compare changed addresses with previously enumerated static store superset'],'environment':{'main_sha256':session['before'],'emulator':'DOSBox-X','load_base':hex(result['entry']['CS'])},'claims':[{'text':f'DS:0043 before={before[1]}, after={after[1]}; {len(diff)} bytes changed in captured scenario buffer; {len(outside)} changed addresses outside static store superset. This is one run only.','confidence':'observed','evidence_ids':['before','after','comparison','static']},{'text':f'Pre-helper buffer matches complete SCEDATA slice at file offsets {matches}.','confidence':'confirmed','evidence_ids':['before','source','comparison']}],'evidence':evidence,'human_summary_ru':f'Измерены два буфера по 8143 байта. DS:0043 {before[1]} → {after[1]}; изменено {len(diff)} байт. Интервал включает close и helper; универсальное сохранение поля не доказано.','open_questions':['Other scenario inputs and branches untested','Memory outside captured buffer unobserved','Individual writes not traced; unchanged bytes may have been rewritten'],'next_step':'Run a different natural scenario selection and repeat; correlate changed fields with static store sites without assigning gameplay semantics.'}
    except AssertionError as e:
        print(json.dumps({'ok': False, 'script': NAME, 'error': str(e) or repr(e)}))
        return 1
    pairs = []
    if args.write_report:
        pairs = [(run/'comparison.json', cmp_text), (Path(args.write_report), json.dumps(report,ensure_ascii=False,indent=2)+'\n')]
    code = save(pairs, args.force)
    if code:
        return code
    verdict = {'ok': True, 'script': NAME, **{k:v for k,v in measurement.items() if k!='changed_bytes'}}
    if args.write_report:
        verdict['report'] = args.write_report
    print(json.dumps(verdict))
    return 0


if __name__ == '__main__':
    sys.exit(main())
