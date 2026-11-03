"""Lossless structural SCEDATA parser. Undecoded bytes stay opaque.

Only selector_raw (+1) has an established runtime relation to MAPINF.
The calendar interpretation of +2..+6 is a candidate, not a proven schema.
No resource text or record bodies are printed by the verification command.
"""
from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TEXT_SIZE=800
TEXT_COUNT=12
RECORD_SIZE=8143
HEADER_SIZE=TEXT_SIZE*TEXT_COUNT
# Record arrays: name -> (offset in record, element size, count). The record is loaded at DS:0x42,
# so DS = offset + 0x42; bases and strides come from the save pointer code (docs/SAVEDATA_FORMAT.md).
ARRAYS=dict(sides=(0x1D8,65,2), officers=(0x25A,31,44), regiments=(0x7BA,13,256),
            divisions=(0x14BA,22,64), cities=(0x1A3A,68,21))

@dataclass(frozen=True)
class Record:
    tag: int
    selector_raw: int
    calendar_candidate: bytes
    opaque_tail: bytes
    @property
    def map_index(self):
        return self.selector_raw&127
    @classmethod
    def parse(cls, raw):
        if len(raw)!=RECORD_SIZE: raise ValueError('Record must contain 8143 bytes')
        return cls(raw[0],raw[1],raw[2:7],raw[7:])
    def array(self, name):
        off,size,count=ARRAYS[name]
        raw=self.build()
        return tuple(raw[off+i*size:off+(i+1)*size] for i in range(count))
    def city(self, i):
        r=self.array('cities')[i]
        w=lambda o: int.from_bytes(r[o:o+2],'little')
        return dict(name=r[:20].split(b'\0')[0], fuel=w(23), ammo=w(25), food=w(27), endurance=(r[35],r[36]))
    def division(self, i):
        r=self.array('divisions')[i]
        first=int.from_bytes(r[0:2],'little')
        # x, y: cell of the 40x40 map (16db:1eea); +0x15 bit 2 = on map, bit 0 = army HQ.
        return dict(first_regiment=None if first==0xFFFF else first, x=r[2], y=r[3], kind=r[21])
    def regiment(self, i):
        r=self.array('regiments')[i]
        nxt=int.from_bytes(r[0:2],'little')
        return dict(next=None if nxt==0xFFFF else nxt, type=r[2], strength=int.from_bytes(r[3:5],'little'))
    def build(self):
        if len(self.calendar_candidate)!=5 or len(self.opaque_tail)!=RECORD_SIZE-7:
            raise ValueError('Invalid field lengths')
        return bytes((self.tag,self.selector_raw))+self.calendar_candidate+self.opaque_tail

@dataclass(frozen=True)
class Scedata:
    texts: tuple
    records: tuple
    @classmethod
    def parse(cls,raw):
        if len(raw)<HEADER_SIZE or (len(raw)-HEADER_SIZE)%RECORD_SIZE:
            raise ValueError('Invalid SCEDATA framing')
        return cls(tuple(raw[n:n+TEXT_SIZE] for n in range(0,HEADER_SIZE,TEXT_SIZE)),
            tuple(Record.parse(raw[n:n+RECORD_SIZE]) for n in range(HEADER_SIZE,len(raw),RECORD_SIZE)))
    def build(self):
        if len(self.texts)!=12 or any(len(t)!=800 for t in self.texts):
            raise ValueError('Invalid text framing')
        return b''.join(self.texts)+b''.join(r.build() for r in self.records)

def verify(source,out):
    raw=source.read_bytes(); parsed=Scedata.parse(raw)
    rows=[]
    for i,r in enumerate(parsed.records):
        offset=HEADER_SIZE+i*RECORD_SIZE
        original=raw[offset:offset+RECORD_SIZE]
        built=r.build()
        assert built==original
        rows.append(dict(record=i,file_offset=offset,size=len(built),selector_raw=r.selector_raw,
            masked_map_index=r.map_index,sha256=hashlib.sha256(original).hexdigest(),round_trip_equal=True))
    assert parsed.build()==raw
    # Reject truncation and malformed framing, including lost trailing bytes.
    for malformed in (raw[:-1],raw+b'\0',raw[:9599]):
        try: Scedata.parse(malformed)
        except ValueError: pass
        else: raise AssertionError('Malformed framing accepted')
    result=dict(source=str(source.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),
        text_blocks=len(parsed.texts),records=rows,whole_file_round_trip_equal=True,
        scope='Structural parser: tag and selector bytes, five opaque calendar-candidate bytes, opaque tail; no gameplay field semantics claimed')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(records=len(rows),round_trip_equal=True,evidence=str(out))))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=ROOT/'private/game-dos-working/scedata')
    ap.add_argument('--out',type=Path,default=ROOT/'artifacts/experiments/SCEPARSE-20261031/roundtrip.json')
    a=ap.parse_args(); verify(a.source,a.out)
