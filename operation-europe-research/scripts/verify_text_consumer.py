"""Verify TASK-020 Ghidra exports with MZ relocation-aware comparison."""
import csv,hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/experiments/TASK-020'
source=ROOT/'private/game-dos/main.exe'
raw=source.read_bytes();loaded=bytearray(raw)
header=struct.unpack_from('<H',raw,8)[0]*16
table=struct.unpack_from('<H',raw,24)[0]
for i in range(struct.unpack_from('<H',raw,6)[0]):
    off,seg=struct.unpack_from('<HH',raw,table+4*i);pos=header+16*seg+off
    struct.pack_into('<H',loaded,pos,(struct.unpack_from('<H',raw,pos)[0]+0x1000)&65535)
summary={};evidence=[]
for name in ('prelude','buffer','consumer'):
    path=OUT/(name+'.tsv')
    rows=list(csv.DictReader(path.read_text().splitlines(),delimiter='\t'))
    ins=[r for r in rows if r['kind']=='insn']
    for r in ins:
        off=int(r['file_offset'],16);b=bytes.fromhex(r['bytes_or_target'])
        assert loaded[off:off+len(b)]==b,(name,r['file_offset'])
    summary[name]={'instructions_verified':len(ins),'outside':[r['ghidra'] for r in rows if r['kind']=='outside'],'missing':[r['ghidra'] for r in rows if r['kind']=='missing'],'computed':[r['ghidra'] for r in rows if r['kind']=='computed'],'calls':[r['bytes_or_target'] for r in rows if r['kind']=='call']}
    evidence.append({'id':name,'path':str(path.relative_to(ROOT)),'kind':'relocation-verified disassembly','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
assert not summary['buffer']['outside'] and not summary['buffer']['missing']
(OUT/'measurement.json').write_text(json.dumps(summary,indent=2)+'\n')
evidence.append({'id':'measurement','path':str((OUT/'measurement.json').relative_to(ROOT)),'kind':'verification','sha256':hashlib.sha256((OUT/'measurement.json').read_bytes()).hexdigest()})
report={'schema_version':'1','task_id':'TASK-020','status':'COMPLETED','goal':'Trace candidate consumer of scenario text buffer','methods':['Read-only bounded CFG export, no callee traversal','Verify bytes against main.exe with loader MZ relocations +0x1000'],'environment':{'main_sha256':hashlib.sha256(raw).hexdigest(),'ghidra':'12.2','runtime':'No execution for these consumer functions'},'claims':[{'text':'1000:8472 preserves incoming BX in SI and passes it as BX to 1000:4c84 after setup calls. Export contains 20 verified instructions and RETF, no out-of-range successors. Callee preservation contracts not independently established.','confidence':'observed','evidence_ids':['buffer','measurement']},{'text':'1000:4c84 reads byte [BX], tests zero, compares byte values 0x20,0x1b,0x81,0xd8 and tracks buffer pointers. Text/control-sequence processing is plausible; actual glyph rendering is not yet proven. The export omits five successor addresses outside its bound.','confidence':'inferred','evidence_ids':['consumer','measurement']}],'evidence':evidence,'human_summary_ru':'Прослежен кандидат потребителя текста: 8472 → 4c84. В последнем есть обработка нуля, пробела, ESC и диапазона байтов. Это гипотеза текстового парсера, не доказательство вывода на экран. Все 171 экспортированные инструкции сверены с релокациями.','open_questions':['Runtime pointer equality with 800-byte read buffer','Five omitted CFG successors in consumer','Callee register preservation and eventual glyph renderer'],'next_step':'Capture BX at 1000:8472 and 1000:4c84 and compare 800-byte buffer with verified SCEDATA slice; complete consumer CFG later.'}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary))
