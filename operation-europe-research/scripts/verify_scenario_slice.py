"""Verify TASK-011 runtime SCEDATA slice against source; no model judgment."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
run=Path(sys.argv[1]).resolve()
result=json.loads((run/'result.json').read_text())
session=json.loads((run/'session.json').read_text())
hits={h['tag']:h for h in result['hits']}
assert not result['timed_out'] and session['unchanged']
entry=hits['slice-entry']['registers']
seek=hits['slice-seek']['registers']
read=hits['slice-read']['registers']
al=entry['AX']&255
offset=max(al-1,0)*800
source=ROOT/'private/game-dos-working/scedata'
data=source.read_bytes()
raw=(run/'slice-read-name.bin').read_bytes()
assert len(raw)==800 and raw==data[offset:offset+800]
assert (seek['DX']<<16|seek['AX'])==offset
assert read['AX']==800 and read['DX']==entry['BX']
assert hits['slice-open']['registers']['AX']==9
assert (run/'slice-name-name.bin').read_bytes().split(b'\0')[0]==b'SCEDATA'
evidence=[]
for id,path in [('result',run/'result.json'),('session',run/'session.json'),('commands',run/'commands.json'),('buffer',run/'slice-read-name.bin'),('name',run/'slice-name-name.bin'),('source',source),('static',ROOT/'artifacts/experiments/JEV-003/functions.tsv')]:
    evidence.append({'id':id,'path':str(path.relative_to(ROOT)),'kind':'local evidence','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
report={'schema_version':'1','task_id':'TASK-011','status':'COMPLETED','goal':'Runtime verification of Jev-prioritized 800-byte SCEDATA reader',
 'methods':['DOSBox-X loopback debugger and AUTOTYPE','Breakpoints image offsets 71C6,71E4,71ED,71F6,7208; measured MZ load base','Complete buffer comparison and seek/read register validation'],
 'environment':{'main_sha256':session['before'],'load_base':hex(result['entry']['CS']),'emulator':'DOSBox-X','input':'space enter enter enter'},
 'claims':[{'text':f'For entry AL={al}, function file 0xD1C6 opens SCEDATA, returns handle 9, seeks to {offset}, reads 800 bytes into DS:{entry["BX"]:04x}. Entire buffer equals SCEDATA file slice at {offset}. DS=SS={entry["DS"]:04x}.','confidence':'confirmed','evidence_ids':['result','buffer','source','name','static']},{'text':'The 800-byte text-like region at start of SCEDATA is actively read by game code. Meaning of all twelve candidate regions and total scenario count remain unknown.','confidence':'observed','evidence_ids':['result','buffer','source']}],
 'evidence':evidence,'human_summary_ru':'Подтверждён выбранный Jev кандидат: при AL=1 игра читает первые 800 байт SCEDATA, полный буфер совпал. Это связывает ранее найденные 800-байтовые участки с реальным чтением. CF отдельно не измерен. GUI не использовался, скриншот не снимался.',
 'open_questions':['Other AL values not exercised','Callers and displayed meaning of text not traced','No claim that 12 slices equal 12 playable scenarios','Comparative cloud-labor saving from Jev remains unmeasured'],
 'next_step':'Capture another naturally selected slice or trace callers; then compare scenario DS:0043 before/after helper.'}
(run.parent/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'verified':True,'entry_al':al,'file_offset':offset,'read_bytes':800,'buffer':f'{entry["DS"]:04x}:{entry["BX"]:04x}','report':str(run.parent/'report.json')}))
