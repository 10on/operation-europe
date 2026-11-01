"""Bounded Jev triage versus an existing deterministic MOV-store filter."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/experiments/JEV-002'
SOURCE=ROOT/'artifacts/experiments/TASK-008/helper-flow.tsv'
GOLD=ROOT/'artifacts/experiments/TASK-009/measurement.json'

def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def prepare():
    OUT.mkdir(exist_ok=True)
    if (OUT/'batch.json').exists(): raise ValueError('Do not overwrite prepared experiment')
    rows=[r for r in csv.DictReader(SOURCE.read_text().splitlines(),delimiter='\t') if r['kind']=='insn']
    binary=(ROOT/'private/game-dos/main.exe').read_bytes()
    gold={int(r['store_file_offset'],16) for r in json.loads(GOLD.read_text())['store_formulas']}
    for r in rows:
        off=int(r['file_offset'],16); b=bytes.fromhex(r['bytes_or_target'])
        assert binary[off:off+len(b)]==b
    started=time.perf_counter()
    selected={int(r['file_offset'],16) for r in rows if r['asm'].startswith('MOV ') and '[' in r['asm'].split(',')[0] and '[BP ' not in r['asm'].split(',')[0]}
    elapsed=(time.perf_counter()-started)*1000
    assert selected==gold
    positives=[r for r in rows if int(r['file_offset'],16) in gold]
    negatives=[]
    # Four stack stores, two memory reads, two address calculations.
    for pred,count in [(lambda a:a.startswith('MOV ') and '[' in a.split(',')[0] and 'BP' in a.split(',')[0],4),(lambda a:a.startswith('MOV ') and '[' not in a.split(',')[0] and '[' in a,2),(lambda a:a.startswith('LEA '),2)]:
        negatives.extend([r for r in rows if pred(r['asm'])][:count])
    for r in rows:
        if len(negatives)>=8: break
        if r not in negatives and r not in positives: negatives.append(r)
    sample=sorted(positives+negatives,key=lambda r:int(r['file_offset'],16))
    assert len(sample)==16
    criteria={'candidate':'MOV writes an explicit memory destination using default DS; retain for data-write investigation','exclude':'Other instruction, register destination, or BP-based default SS memory destination; exclude from this specific list','unresolved':'Cannot classify from this instruction'}
    questions={f'c{i:02}':{'type':'choice','instructions':f'Classify candidate c{i:02} under the stated rule.','criteria':criteria} for i in range(len(sample))}
    state={'scope':'16-bit x86 Intel operand order destination,source. Find nonstack explicit MOV stores only. PUSH and implicit stack effects are outside scope. BP-based addressing defaults to SS, other unoverridden memory addressing to DS. Do not infer field meaning or runtime alias safety.','candidates':{f'c{i:02}':r['asm'] for i,r in enumerate(sample)}}
    expected={f'c{i:02}':'candidate' if int(r['file_offset'],16) in gold else 'exclude' for i,r in enumerate(sample)}
    save(OUT/'batch.json',{'request':{'model':'jev-1.14.0','state':state,'questions':questions},'expected':expected})
    save(OUT/'baseline.json',{'binary_sha256':hashlib.sha256(binary).hexdigest(),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'gold_sha256':hashlib.sha256(GOLD.read_bytes()).hexdigest(),'instructions':len(rows),'selected':len(selected),'filter_ms':elapsed,'sample':sample,'selection_note':'Balanced diagnostic sample selected against previously reviewed gold, not blind discovery.'})
    print(json.dumps({'instructions':len(rows),'sample':len(sample),'local_filter_ms':elapsed,'local_correct':selected==gold}))

def score(log):
    log=log.resolve()
    record=json.loads(log.read_text()); baseline=json.loads((OUT/'baseline.json').read_text())
    assert record['status']=='completed'
    assert record['request']==json.loads((OUT/'batch.json').read_text())['request']
    grade=record['grade']; tp=fp=fn=0
    for g in grade.values():
        tp+=g['expected']=='candidate' and g['actual']=='candidate'
        fp+=g['expected']!='candidate' and g['actual']=='candidate'
        fn+=g['expected']=='candidate' and g['actual']!='candidate'
    summary={'correct':sum(g['correct'] for g in grade.values()),'total':len(grade),'tp':tp,'fp':fp,'fn':fn,'jev_ms':record['elapsed_ms'],'local_filter_ms':baseline['filter_ms'],'estimated_cost_usd':record.get('estimated_cost_usd'),'utility':'No incremental utility demonstrated: existing local filter exactly recovered all 8 gold sites from 246 instructions. Diagnostic sample is not blind. Do not deploy Jev for this operation.'}
    save(OUT/'comparison.json',summary)
    evidence=[]
    for id,path in [('baseline',OUT/'baseline.json'),('comparison',OUT/'comparison.json'),('batch',OUT/'batch.json'),('call',log)]:
        evidence.append({'id':id,'path':str(path.relative_to(ROOT)),'kind':'experiment','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    save(OUT/'report.json',{'schema_version':'1','task_id':'JEV-002','status':'COMPLETED','goal':'Оценить Jev для фильтрации nonstack MOV stores против локального фильтра','methods':['Byte verification against original','16-case diagnostic sample against preexisting reviewed gold','Deterministic filter over all 246 instructions'],'environment':{'model':'jev-1.14.0'},'claims':[{'text':summary['utility'],'confidence':'observed','evidence_ids':['baseline','comparison','call']}],'evidence':evidence,'human_summary_ru':f'Jev {summary["correct"]}/16; TP={tp}, FP={fp}, FN={fn}. Локальный фильтр находит все 8 известных сайтов. Дополнительная польза Jev не показана.','open_questions':['Может ли Jev помогать в семантической классификации, где точный фильтр отсутствует?','Экономия облачных токенов здесь не измерена.'],'next_step':'В реверсе использовать локальный фильтр. Для Jev выбирать семантические кандидаты с независимо проверяемым результатом; не расширять бюджет на основании этого теста.'})
    print(json.dumps(summary))

if __name__=='__main__':
    if len(sys.argv)==1: prepare()
    else: score(Path(sys.argv[1]))
