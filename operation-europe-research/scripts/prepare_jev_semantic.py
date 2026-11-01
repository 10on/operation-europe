"""Prepare unlabeled semantic triage without reading candidate bodies into cloud context."""
import csv,hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/experiments/JEV-003'
rows=list(csv.DictReader((OUT/'functions.tsv').read_text().splitlines(),delimiter='\t'))
binary=(ROOT/'private/game-dos/main.exe').read_bytes()
relocated=bytearray(binary)
count=struct.unpack_from('<H',binary,6)[0]
table=struct.unpack_from('<H',binary,24)[0]
header=struct.unpack_from('<H',binary,8)[0]*16
for i in range(count):
    off,seg=struct.unpack_from('<HH',binary,table+i*4)
    pos=header+seg*16+off
    word=struct.unpack_from('<H',binary,pos)[0]
    struct.pack_into('<H',relocated,pos,(word+0x1000)&65535)
groups={}
for r in rows:
    groups.setdefault(r['candidate'],[]).append(r)
    if r['ghidra']=='END':continue
    off=int(r['file_offset'],16);raw=bytes.fromhex(r['bytes'])
    assert relocated[off:off+len(raw)]==raw, (r['candidate'],r['file_offset'])
state={'context':'DOS x86 Intel syntax. Candidates found by conventional prologue, not proven full function boundaries. Snippets omit instructions. Classify evidence visible here; uncertain is allowed. Known callees: 1000:001e DOS open; 1000:0043 DOS read; 1000:009b DOS seek; 1000:0032 DOS close; 1977:000e or 1000:977e open wrapper. File loading could be scenario, messages, graphics; do not identify file from numeric pointer alone.','candidates':{}}
manifest={}
for k,rs in groups.items():
    ins=[r for r in rs if r['ghidra']!='END']
    # Fixed selection rule independent of labels: first 10 plus CALLs/INTs and last 3.
    chosen=ins[:10]+[r for r in ins[10:-3] if r['asm'].startswith(('CALL','INT '))]+ins[-3:]
    state['candidates'][k]='; '.join(r['asm'] for r in chosen[:22])
    manifest[k]={'entry':rs[0]['entry'],'file_offset':ins[0]['file_offset'],'instructions':len(ins),'excerpt_instructions':len(chosen[:22]),'end':rs[-1]['asm']}
criteria={'file_io':'Visible calls support file opening, reading, seeking or closing; prioritize file-data tracing','interface':'Visible evidence primarily supports drawing, text presentation or user input','data_transform':'Visible evidence primarily supports arithmetic or copying/transforming records without clear I/O','unresolved':'Insufficient visible evidence to identify primary role'}
questions={k:{'type':'choice','instructions':'Classify only candidate '+k+'. Choose unresolved rather than guessing from numeric constants.','criteria':criteria} for k in groups}
batch={'request':{'model':'jev-1.14.0','state':state,'questions':questions},'expected':None}
(OUT/'batch.json').write_text(json.dumps(batch,indent=2)+'\n')
(OUT/'manifest.json').write_text(json.dumps({'binary_sha256':hashlib.sha256(binary).hexdigest(),'candidate_source':'prologue scan after reviewed region; possible false boundaries','groups':manifest},indent=2)+'\n')
print(json.dumps({'candidates':len(groups),'request_bytes':len(json.dumps(batch['request']).encode()),'verified_instructions':sum(r['ghidra']!='END' for r in rows)}))
