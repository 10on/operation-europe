"""Post-response review of JEV-003; preserves unresolved as abstention."""
import csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/experiments/JEV-003'
def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
rows=list(csv.DictReader((OUT/'functions.tsv').read_text().splitlines(),delimiter='\t'))
groups={}
for r in rows: groups.setdefault(r['candidate'],[]).append(r)
callpath=ROOT/'artifacts/experiments/JEV-001/call-010.json'
call=json.loads(callpath.read_text())
assert call['status']=='completed'
answers={k:v['choice'] for k,v in call['response']['answers'].items()}
assert call['request']==json.loads((OUT/'batch.json').read_text())['request']
review={}
for key in ('f00','f01','f02'):
    body=[r['asm'] for r in groups[key]]
    assert 'CALLF 0x1000:977e' in body
    review[key]={'model':answers[key],'review':'file_io','basis':'Verified known open wrapper call in full exported body; file purpose still needs evidence.'}
assert all(answers[k]=='file_io' for k in review)
for key in ('f03','f07','f10','f11'):
    review[key]={'model':answers[key],'review':'unresolved','basis':'No proven I/O callee semantics; absence in truncated/partial graph is not exclusion.'}
review['f11']['secondary_observation']='Complete exported linear body computes stride 31 and copies/transforms fields +0x13,+0x14,+0x15,+0x17,+0x18,+0x19,+0x1a through helper 1000:79d0. Meaning and helper semantics unknown.'
binary=(ROOT/'private/game-dos/main.exe').read_bytes()
strings={}
for ptr in (0x2e8c,0x2f48,0x2ec4):
    off=0x4d120+ptr
    strings[hex(ptr)]={'file_offset':hex(off),'ascii':binary[off:off+64].split(b'\0')[0].decode('ascii'),'confidence':'inferred DS mapping outside measured runtime sites'}
body=[r['asm'] for r in groups['f00']]
for required in ['OR AL,AL','DEC byte ptr [BP + -0x6]','SUB AH,AH','MOV CX,0x320','MUL CX','MOV AX,0x320','CALLF 0x1000:0043']:
    assert required in body
arithmetic=[{'al':al,'offset':(al-1 if al else 0)*800} for al in range(256)]
save('review.json',{'answers':answers,'reviewed':review,'candidate_strings':strings,'f00_seek_cases':arithmetic,'scope':'Post-response code review; not blinded and no matched control arm. Unresolved is abstention, never a negative classification.','finding':'f00 requests 800-byte read after seek max(unsigned input AL-1,0)*800; filename SCEDATA inferred from pointer, runtime untested.','efficiency':'3 positive candidates confirmed, 9 abstentions. 4 abstentions reviewed; unresolved semantic role remains. No measured cloud-token saving; setup and retries substantial.'})
evidence=[]
for id,path in [('export',OUT/'functions.tsv'),('manifest',OUT/'manifest.json'),('batch',OUT/'batch.json'),('response',callpath),('review',OUT/'review.json')]:
    evidence.append({'id':id,'path':str(path.relative_to(ROOT)),'kind':'local analysis','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
save('report.json',{'schema_version':'1','task_id':'JEV-003','status':'COMPLETED','goal':'Prospective Jev candidate triage before inspecting full exports','methods':['12 prologue candidates, bounded exports; first 10 instructions plus calls and tail sent to Jev','289 instructions verified against MZ image with loader relocations +0x1000','Post-response review of all 3 selected and 4 of 9 abstentions','256-value arithmetic enumeration for f00'],'environment':{'model':'jev-1.14.0','binary_sha256':hashlib.sha256(binary).hexdigest(),'runtime':'No game execution in this experiment'},'claims':[{'text':'Jev selected f00-f02 as file I/O; all three contain the previously verified open wrapper. Nine unresolved answers are abstentions. Precision on 3 reviewed selections is 3/3; recall and labor savings not established.','confidence':'observed','evidence_ids':['response','review','export']},{'text':'Candidate f00 at file 0xD1C6 requests 800-byte read, seek offset max(unsigned incoming AL-1,0)*800. Pointer 0x2E8C is consistent with SCEDATA; no runtime filename or read result measured here.','confidence':'inferred','evidence_ids':['export','review']}],'evidence':evidence,'human_summary_ru':'Jev предложил 3 кандидата, все содержат файловый open. Обнаружен кандидат чтения 800-байтовых участков SCEDATA. 9 воздержаний не означают исключения. Экономия труда не доказана: нет контрольной группы, были затраты на экспорт и исправления.','open_questions':['Runtime DS and successful 800-byte read for f00','Semantics of helper 1000:79d0 and record stride 31','Five abstentions not reviewed; no recall estimate','Export is bounded and not a complete CFG'],'next_step':'Catch f00 read at runtime or trace its callers; test the 800-byte SCEDATA region hypothesis. Reuse export harness for next triage, with a predeclared control and effort accounting.'})
print(json.dumps({'selected_verified':3,'abstained':9,'abstentions_reviewed':4,'new_candidate':'800-byte SCEDATA slice reader','strings':strings,'report':str(OUT/'report.json')}))
