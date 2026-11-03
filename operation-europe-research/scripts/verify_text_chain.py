"""Check runtime pointer and full buffer identity along text consumer chain.

Default: checks only, prints a one-line JSON verdict, writes nothing.
--write-report PATH: writes the report JSON to PATH (refuses to overwrite unless --force).
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = 'verify_text_chain'


def save(pairs, force):
    for path, _ in pairs:
        if path.exists() and not force:
            print(f'refusing to overwrite {path} (use --force)', file=sys.stderr)
            return 2
    for path, text in pairs:
        path.write_text(text, encoding='utf-8')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Check runtime pointer and buffer identity along text consumer chain. Writes nothing unless --write-report.')
    ap.add_argument('run', help='runtime capture directory')
    ap.add_argument('--write-report', metavar='PATH', help='write report JSON to PATH')
    ap.add_argument('--force', action='store_true', help='overwrite existing output files')
    args = ap.parse_args(argv)
    run = Path(args.run).resolve()
    try:
        result=json.loads((run/'result.json').read_text())
        session=json.loads((run/'session.json').read_text())
        assert session['unchanged'] and not result['timed_out']
        hits={h['tag']:h for h in result['hits']}
        tags=['text-source','text-wrapper','text-consumer']
        buffers={tag:(run/(tag+'-name.bin')).read_bytes() for tag in tags}
        source=ROOT/'private/game-dos-working/scedata'
        expected=source.read_bytes()[:800]
        assert all(len(b)==800 and b==expected for b in buffers.values())
        ptr=hits['text-source']['registers']['DX']
        ds=hits['text-source']['registers']['DS']
        assert all(hits[tag]['registers']['BX']==ptr and hits[tag]['registers']['DS']==ds for tag in tags[1:])
        assert hits['text-source']['registers']['AX']==800
        evidence=[]
        for id,path in [('result',run/'result.json'),('commands',run/'commands.json'),('session',run/'session.json'),('source',source)]+[(tag,run/(tag+'-name.bin')) for tag in tags]:
            evidence.append({'id':id,'path':str(path.relative_to(ROOT)),'kind':'local evidence','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        report={'schema_version':'1','task_id':'TASK-021','status':'COMPLETED','goal':'Trace actual 800-byte SCEDATA buffer to candidate text consumer','methods':['Sequentially arm breakpoints after read, at wrapper entry and consumer entry','Capture DS:DX after read and DS:BX at both entries','Compare all 800 bytes and pointer identity against SCEDATA file[0:800]'],'environment':{'main_sha256':session['before'],'emulator':'DOSBox-X','load_base':hex(result['entry']['CS'])},'claims':[{'text':f'In this run the same pointer {ds:04x}:{ptr:04x} and identical 800-byte SCEDATA file[0:800] content pass from read return image7208 to wrapper image8472 and consumer image4C84.','confidence':'confirmed','evidence_ids':['result','text-source','text-wrapper','text-consumer','source']}],'evidence':evidence,'human_summary_ru':'Один и тот же 800-байтовый текст SCEDATA без изменений дошёл до 8472 и 4C84. Роль 4C84 как потребителя этого текста подтверждена; фактический вывод глифов на экран ещё не проверен.','open_questions':['Eventual glyph output and formatting semantics','Other text slices and control-byte branches','Complete consumer CFG has not been exported'],'next_step':'Complete bounded consumer CFG and trace character output callee; preserve distinction between string processing and visible rendering.'}
    except AssertionError as e:
        print(json.dumps({'ok': False, 'script': NAME, 'error': str(e) or repr(e)}))
        return 1
    pairs = [(Path(args.write_report), json.dumps(report,ensure_ascii=False,indent=2)+'\n')] if args.write_report else []
    code = save(pairs, args.force)
    if code:
        return code
    verdict = {'ok': True, 'script': NAME, 'verified_stages':3,'same_pointer':f'{ds:04x}:{ptr:04x}','same_bytes':800,'file_offset':0}
    if args.write_report:
        verdict['report'] = args.write_report
    print(json.dumps(verdict))
    return 0


if __name__ == '__main__':
    sys.exit(main())
