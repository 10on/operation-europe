"""Check runtime pointer and full buffer identity along text consumer chain."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
run=Path(sys.argv[1]).resolve()
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
(run.parent/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'verified_stages':3,'same_pointer':f'{ds:04x}:{ptr:04x}','same_bytes':800,'file_offset':0}))
