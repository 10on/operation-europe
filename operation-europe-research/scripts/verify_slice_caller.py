"""Recover far-return caller from captured stack, check original call bytes."""
import hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
run=Path(sys.argv[1]).resolve()
result=json.loads((run/'result.json').read_text())
session=json.loads((run/'session.json').read_text())
assert session['unchanged'] and not result['timed_out']
hit=result['hits'][0];base=result['entry']['CS']
stack=(run/'entry-stack.bin').read_bytes()
ip,cs=struct.unpack_from('<HH',stack)
return_image=(cs-base)*16+ip
return_file=return_image+0x6000
source=ROOT/'private/game-dos/main.exe';data=source.read_bytes()
assert hashlib.sha256(data).hexdigest()==session['before']
candidates=[]
if data[return_file-3]==0xe8:
    displacement=struct.unpack_from('<h',data,return_file-2)[0]
    target_image=(cs-base)*16+((ip+displacement)&65535)
    if target_image==0x71c6 and data[return_file-4]==0x0e:
        candidates.append({'kind':'PUSH CS; near CALL','call_file_offset':hex(return_file-3),'push_cs_file_offset':hex(return_file-4),'target_image_offset':hex(target_image),'bytes_hex':data[return_file-4:return_file].hex()})
if data[return_file-5]==0x9a:
    ti,ts=struct.unpack_from('<HH',data,return_file-4)
    if ts*16+ti==0x71c6:
        candidates.append({'kind':'CALL FAR (unrelocated target)','call_file_offset':hex(return_file-5),'target_image_offset':hex(ts*16+ti),'bytes_hex':data[return_file-5:return_file].hex()})
assert len(candidates)==1, candidates
measurement={'runtime_return':f'{cs:04x}:{ip:04x}','return_file_offset':hex(return_file),'load_base':hex(base),'verified_call':candidates[0],'entry_ax':hit['registers']['AX'],'entry_bx':hex(hit['registers']['BX']),'stack_address':f'{hit["registers"]["SS"]:04x}:{hit["registers"]["SP"]:04x}','source_sha256':hashlib.sha256(data).hexdigest()}
(run/'caller.json').write_text(json.dumps(measurement,indent=2)+'\n')
evidence=[]
for id,path in [('stack',run/'entry-stack.bin'),('result',run/'result.json'),('session',run/'session.json'),('caller',run/'caller.json'),('source',source)]:
    evidence.append({'id':id,'path':str(path.relative_to(ROOT)),'kind':'local evidence','sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
report={'schema_version':'1','task_id':'TASK-019','status':'COMPLETED','goal':'Locate actual caller of 800-byte SCEDATA reader','methods':['Stop at function entry before prologue','Read 16 bytes SS:SP through native debugger','Decode far-return IP:CS; verify preceding CALL and target against original MZ bytes'],'environment':{'emulator':'DOSBox-X','main_sha256':session['before'],'load_base':hex(base)},'claims':[{'text':json.dumps(measurement),'confidence':'confirmed','evidence_ids':['stack','result','source','caller']}],'evidence':evidence,'human_summary_ru':'Найден вызывающий участок по runtime-стеку и независимо проверен по байтам CALL. Это один наблюдённый caller, не полный список.','open_questions':['Purpose of caller and downstream text renderer','Other callers and input values not enumerated'],'next_step':'Bounded Ghidra analysis around verified caller; trace caller buffer into display or parsing routine.'}
(run.parent/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(measurement))
