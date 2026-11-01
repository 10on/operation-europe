"""Compare scenario buffers around close/helper interval, preserving scope limits."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
run=Path(sys.argv[1]).resolve()
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
(run/'comparison.json').write_text(json.dumps(measurement,indent=2)+'\n')
evidence=[]
for id,path in [('result',run/'result.json'),('session',run/'session.json'),('before',run/'helper-before-name.bin'),('after',run/'helper-after-name.bin'),('comparison',run/'comparison.json'),('static',static),('source',source)]:
    evidence.append({'id':id,'path':str(path.relative_to(ROOT)),'kind':'local evidence','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
report={'schema_version':'1','task_id':run.parent.name,'status':'COMPLETED','goal':'Measure DS:0043 and scenario buffer across close/helper interval','methods':['Two native debugger breakpoints image 716c and 7180','Full 8143-byte local buffer comparison','Compare changed addresses with previously enumerated static store superset'],'environment':{'main_sha256':session['before'],'emulator':'DOSBox-X','load_base':hex(result['entry']['CS'])},'claims':[{'text':f'DS:0043 before={before[1]}, after={after[1]}; {len(diff)} bytes changed in captured scenario buffer; {len(outside)} changed addresses outside static store superset. This is one run only.','confidence':'observed','evidence_ids':['before','after','comparison','static']},{'text':f'Pre-helper buffer matches complete SCEDATA slice at file offsets {matches}.','confidence':'confirmed','evidence_ids':['before','source','comparison']}],'evidence':evidence,'human_summary_ru':f'Измерены два буфера по 8143 байта. DS:0043 {before[1]} → {after[1]}; изменено {len(diff)} байт. Интервал включает close и helper; универсальное сохранение поля не доказано.','open_questions':['Other scenario inputs and branches untested','Memory outside captured buffer unobserved','Individual writes not traced; unchanged bytes may have been rewritten'],'next_step':'Run a different natural scenario selection and repeat; correlate changed fields with static store sites without assigning gameplay semantics.'}
(run.parent/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in measurement.items() if k!='changed_bytes'}))
