"""Verify one TASK-010 runtime capture against local source files; emit report."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    run = Path(sys.argv[1]).resolve()
    result = json.loads((run/'result.json').read_text())
    session = json.loads((run/'session.json').read_text())
    assert session['unchanged'] and not result['timed_out']
    hits = {h['tag']: h for h in result['hits']}
    claims = []
    starts = [int(v,0) for v in sys.argv[2:4]] if len(sys.argv)==4 else [17743,0]
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
    (run.parent/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'verified_reads':2,'report':str(run.parent/'report.json')}))

if __name__=='__main__': main()
