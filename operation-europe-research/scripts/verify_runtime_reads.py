"""Verify one TASK-010 runtime capture against local source files; emit report.

Default: checks only, prints a one-line JSON verdict, writes nothing.
--write-report PATH: writes the report JSON to PATH (refuses to overwrite unless --force).
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = 'verify_runtime_reads'


def save(pairs, force):
    for path, _ in pairs:
        if path.exists() and not force:
            print(f'refusing to overwrite {path} (use --force)', file=sys.stderr)
            return 2
    for path, text in pairs:
        path.write_text(text, encoding='utf-8')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Verify one TASK-010 runtime capture against local source files. Writes nothing unless --write-report.')
    ap.add_argument('run', help='runtime capture directory')
    ap.add_argument('starts', nargs='*', help='optional two file offsets: SCEDATA MAPINF (default 17743 0)')
    ap.add_argument('--write-report', metavar='PATH', help='write report JSON to PATH')
    ap.add_argument('--force', action='store_true', help='overwrite existing output files')
    args = ap.parse_args(argv)
    run = Path(args.run).resolve()
    try:
        result = json.loads((run/'result.json').read_text())
        session = json.loads((run/'session.json').read_text())
        assert session['unchanged'] and not result['timed_out']
        hits = {h['tag']: h for h in result['hits']}
        claims = []
        starts = [int(v,0) for v in args.starts] if len(args.starts)==2 else [17743,0]
        for tag, size, start, ptr in [('scedata',8143,starts[0],0x42),('mapinf',1600,starts[1],0x20b6)]:
            hit = hits[tag+'-read']
            raw = (run/(tag+'-read-name.bin')).read_bytes()
            source = ROOT/'private/game-dos-working'/('scedata' if tag=='scedata' else 'mapinf.dat')
            data = source.read_bytes()
            assert len(raw)==size and raw==data[start:start+size]
            assert hit['registers']['AX']==size
            assert hits[tag+'-open']['registers']['AX']==9
            assert hashlib.sha256(data).hexdigest()==hit['source_sha256']
            assert bytes.fromhex(hits[tag]['name_hex']).split(b'\0')[0].decode()==('SCEDATA' if tag=='scedata' else 'MAPINF.DAT')
            claims.append({'text':f'{tag}: после open AX=9; после read AX={size}. Буфер DS:{ptr:04x} побайтно совпадает с file offset {start}, размер {size}. DS={hit["registers"]["DS"]:04x}. Наблюдение относится к этому запуску.', 'confidence':'observed','evidence_ids':['hits','result','session',tag+'-buffer']})
        evidence=[]
        for ident,path in [('hits',run/'hits.json'),('result',run/'result.json'),('session',run/'session.json'),('commands',run/'commands.json'),('config',run/'config.conf'),('scedata-buffer',run/'scedata-read-name.bin'),('mapinf-buffer',run/'mapinf-read-name.bin')]:
            evidence.append({'id':ident,'path':str(path.relative_to(ROOT)),'kind':'local runtime artifact','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        report={'schema_version':'1','task_id':run.parent.name,'status':'COMPLETED','goal':'Проверить runtime чтение SCEDATA и MAPINF через API DOSBox-X',
                'methods':['Loopback native debugger, verified MZ load base, six breakpoints','AUTOTYPE sequence preserved in config.conf','Full buffer comparison against predeclared expected file offsets'],
                'environment':{'emulator':'DOSBox-X C:/DOSBox-X/dosbox-x.exe','main_sha256':session['before'],'load_base':hex(result['entry']['CS'])},
                'claims':claims,'evidence':evidence,'human_summary_ru':'Оба чтения проверены по AX и полному побайтовому совпадению буфера. Исходный EXE не изменён. Ранее запуски без отдельной консоли завершались до измерений; не считать их успешными.',
                'open_questions':['Carry flag отдельно не измерен.','Смысл полей сценария и геометрия карты неизвестны.','Другие сценарии не проверены.','Скриншоты не сняты: подтверждение по API регистров и памяти, без GUI.'],
                'next_step':'Повторить на другом выбранном сценарии; сопоставить изменившиеся поля и индекс MAPINF. Снять DS:0043 до и после helper.'}
    except AssertionError as e:
        print(json.dumps({'ok': False, 'script': NAME, 'error': str(e) or repr(e)}))
        return 1
    pairs = [(Path(args.write_report), json.dumps(report,ensure_ascii=False,indent=2)+'\n')] if args.write_report else []
    code = save(pairs, args.force)
    if code:
        return code
    verdict = {'ok': True, 'script': NAME, 'verified_reads': 2, 'report': args.write_report}
    print(json.dumps(verdict))
    return 0


if __name__ == '__main__':
    sys.exit(main())
