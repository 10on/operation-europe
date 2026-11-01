"""Batch DOS INT 21h I/O capture via the local DOSBox-X debugger API.

Only the working copy is mounted. No model services or secrets are used.
"""
import argparse
from contextlib import AbstractContextManager
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / 'private'
GAME = PRIVATE / 'game-dos-working'
EXE = Path(r'C:\DOSBox-X\dosbox-x.exe')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class Session(AbstractContextManager):
    def __init__(self, out, keys, port=0):
        self.out, self.keys, self.port = Path(out), keys, port
        self.serial = 0
    def __enter__(self):
        self.out.mkdir(parents=True, exist_ok=True)
        self.commands = (self.out/'commands.jsonl').open('w', encoding='utf-8')
        self.server = socket.socket()
        self.server.bind(('127.0.0.1', self.port))
        self.port=self.server.getsockname()[1]
        self.server.listen(1)
        self.server.settimeout(25)
        self.before = {p.name:sha(p) for p in GAME.iterdir() if p.is_file()}
        config = ('[sdl]\nfullscreen=false\noutput=surface\nwindowposition=50,50\nmaximize=true\nautolock=false\n'
                  '[dosbox]\ntitle=OE IOLOG\nmachine=vgaonly\nmemsize=16\n'
                  f'captures=../artifacts/experiments/IOLOG-20261031/captures\n'
                  f'mcp_server={self.port}\n[cpu]\ncore=normal\ncycles=max\n'
                  '[dos]\nver=6.22\nxms=true\nems=true\numb=true\n'
                  '[sblaster]\nsbtype=none\n[midi]\nmpu401=none\n'
                  '[autoexec]\n@echo off\nmount c game-dos-working\nmount d dos-tools\nc:\nfmdrv\n'
                  +(f'AUTOTYPE -w 5 -p 2 {self.keys}\n' if self.keys else '')+'DEBUGBOX MAIN\n')
        self.config = PRIVATE/f'dosboxx-iolog-{self.port}.conf'
        self.config.write_text(config, encoding='utf-8')
        (self.out/'config.conf').write_text(config, encoding='utf-8')
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 5  # SW_SHOW
        self.proc = subprocess.Popen([str(EXE),'-conf',self.config.name,'-fastlaunch','-nopromptfolder'],
            cwd=PRIVATE, startupinfo=startup, creationflags=subprocess.CREATE_NEW_CONSOLE)
        try:
            self.conn, peer = self.server.accept()
            if peer[0] != '127.0.0.1': raise RuntimeError('Non-loopback peer')
            self.file = self.conn.makefile('r', encoding='utf-8', errors='replace')
            time.sleep(1)
            return self
        except BaseException:
            self.__exit__(None,None,None)
            raise
    def call(self, command, timeout=10):
        self.serial += 1
        n = self.serial
        self.conn.settimeout(timeout)
        self.conn.sendall(f'REQ {n} {command}\n'.encode('ascii'))
        status, lines = None, []
        while True:
            line = self.file.readline()
            if not line: raise ConnectionError(command)
            line = line.rstrip('\r\n')
            if line == f'BEGIN {n} OK': status='OK'
            elif line == f'BEGIN {n} ERR': status='ERR'
            elif line == f'END {n}': break
            elif status is not None: lines.append(line)
        result = dict(command=command, status=status, lines=lines)
        self.commands.write(json.dumps(result)+'\n'); self.commands.flush()
        if status != 'OK': raise RuntimeError(result)
        return lines
    def regs(self, names='CS IP DS ES SS SP AX BX CX DX CF'):
        values = self.call('EXEC EV '+names)[-1].split()
        return dict(zip(names.split(), [int(x,16) for x in values]))
    def dump(self, seg, off, size, target=None):
        dumpname=f'IO{self.port}.BIN'
        self.call(f'EXEC MEMDUMPBIN {seg:04X}:{off:04X} {size:X} {dumpname}')
        data = (PRIVATE/dumpname).read_bytes()
        if len(data)!=size: raise RuntimeError('Short memory dump')
        if target: (self.out/target).write_bytes(data)
        return data
    def key(self,key):
        """Inject one BIOS key into the guest ring, without changing code.

        Caller must pause the guest. This supplies the same scan/ASCII words
        consumed by BIOS INT16 / DOS keyboard input; no host UI is touched.
        """
        codes={'space':0x3920,'enter':0x1c0d,'down':0x5000,'up':0x4800,'esc':0x011b}
        ring=self.dump(0x40,0x1a,4)
        head=int.from_bytes(ring[:2],'little'); tail=int.from_bytes(ring[2:],'little')
        if head!=tail: return False
        if not (0x1e<=tail<0x3e and tail%2==0): raise RuntimeError('Unexpected BIOS ring layout')
        word=codes[key]; newtail=tail+2 if tail+2<0x3e else 0x1e
        self.call(f'EXEC SM 0040:{tail:04X} {word&255:02X} {word>>8:02X}')
        self.call(f'EXEC SM 0040:001C {newtail&255:02X} {newtail>>8:02X}')
        with (self.out/'keys.jsonl').open('a') as f:
            f.write(json.dumps(dict(key=key,head=head,tail=tail,new_tail=newtail,scan_ascii=word))+'\n')
        return True
    def screen(self, tag):
        """Read paused VGA mode-12 planes, restore GC registers; neutral palette.

        This reconstructs the guest frame without Windows capture (which may
        time out). Raw planes and VGA registers remain the primary evidence.
        """
        from PIL import Image
        meta={cmd:self.call('EXEC VGA '+cmd) for cmd in ('DRAW','CRTC','GC','AC')}
        text=' '.join(meta['DRAW'])
        if 'width=640 height=480' not in text: return None
        crtc=' '.join(meta['CRTC'])
        start=int(re.search(r'start-addr=([0-9a-fA-F]+)h',crtc)[1],16)*2
        def inp(port):
            return int(self.call(f'EXEC INP {port:X}')[-1].split()[-1],16)
        index=inp(0x3ce)
        self.call('EXEC OUTP 3CE 4'); plane=inp(0x3cf)
        self.call('EXEC OUTP 3CE 5'); mode=inp(0x3cf)
        planes=[]
        try:
            self.call(f'EXEC OUTP 3CF {mode&~8:X}')
            for n in range(4):
                self.call(f'EXEC OUTP 3CE 4'); self.call(f'EXEC OUTP 3CF {n:X}')
                planes.append(self.dump(0xa000,start,38400,f'{tag}-plane{n}.bin'))
        finally:
            self.call('EXEC OUTP 3CE 4'); self.call(f'EXEC OUTP 3CF {plane:X}')
            self.call('EXEC OUTP 3CE 5'); self.call(f'EXEC OUTP 3CF {mode:X}')
            self.call(f'EXEC OUTP 3CE {index:X}')
        pixels=bytearray(640*480)
        for n,data in enumerate(planes):
            for i,b in enumerate(data):
                for bit in range(8): pixels[i*8+bit]|=((b>>(7-bit))&1)<<n
        im=Image.frombytes('P',(640,480),bytes(pixels))
        im.putpalette([v for i in range(256) for v in (i*17 if i<16 else 0,)*3])
        im.save(self.out/f'{tag}.png')
        self.last_image=im
        meta.update(registers=self.regs(),start_offset=start,palette='neutral grayscale, DAC colors not measured')
        (self.out/f'{tag}.json').write_text(json.dumps(meta,indent=2)+'\n')
        return f'{tag}.png'
    def __exit__(self, *args):
        if getattr(self,'proc',None):
            self.proc.terminate()
            try: self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired: self.proc.kill(); self.proc.wait(timeout=5)
        if getattr(self,'file',None): self.file.close()
        if getattr(self,'conn',None): self.conn.close()
        self.server.close(); self.commands.close()
        after = {p.name:sha(p) for p in GAME.iterdir() if p.is_file()}
        (self.out/'session.json').write_text(json.dumps(dict(before=self.before, after=after,
            unchanged=self.before==after, debugger_sha256=sha(EXE)),indent=2)+'\n')

def probe(out):
    result={}
    with Session(out, 'space enter enter enter') as s:
        result['entry']=s.regs()
        result['flags']=s.call('EXEC EV CF ZF')
        for ah in ('3D','3F','42','3E'): s.call('EXEC BPINT 21 '+ah)
        result['breakpoints']=s.call('EXEC BPLIST')
        s.call('EXEC RUN')
        deadline=time.monotonic()+35
        samples=[]
        while time.monotonic()<deadline:
            time.sleep(.25)
            r=s.regs()
            if r['AX']>>8 in (0x3d,0x3e,0x3f,0x42):
                samples.append(r)
                if len(samples)>1 and samples[-1]==samples[-2]: break
        result['samples']=samples[-3:]
        result['stop']=r
        r=result['stop']
        result['code']=s.dump(r['CS'],r['IP'],8).hex()
        result['stack']=s.dump(r['SS'],r['SP'],16).hex()
        s.call(f'EXEC BP {r["CS"]:04X}:{(r["IP"]+2)&65535:04X}')
        s.call('EXEC RUN')
        time.sleep(.3)
        result['return']=s.regs()
        result['return_cf']=s.call('EXEC EV CF')
        (Path(out)/'probe.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

def capture(out, scenario, seconds=150, menu=False, keys_override=None, adaptive=False):
    # Same menu route as oe-boot keyboard: one player, Allies, field map,
    # view battles, very easy, default abilities, seven consecutive officers.
    keys='space enter '+('down '*scenario)+', , , '
    if not menu:
        keys+='enter enter down enter '+('enter '*6)+'enter '+('down enter '*6)+('enter '*13)
    if keys_override is not None: keys=keys_override
    route=['space','enter']+['down']*scenario
    if not menu: route+=['enter','enter','down','enter']+['enter']*6+['enter']+['down','enter']*6+['enter']*3
    if (Path(out)/'io.jsonl').exists(): raise FileExistsError(f'Use a fresh output directory: {out}')
    handles={}
    count=0
    sites={}
    summary=dict(scenario_downs=scenario, events=0, read_mismatches=0, complete=False)
    with Session(out,'' if adaptive else keys) as s, (Path(out)/'io.jsonl').open('w',encoding='utf-8') as log:
        entry=s.regs()
        summary['load_base_segment']=entry['CS']
        if entry['IP']!=0x409c: raise RuntimeError('Unexpected MAIN entry')
        for ah in ('3D','3F','42','3E'): s.call('EXEC BPINT 21 '+ah)
        s.call('EXEC RUN')
        started=last_progress=time.monotonic()
        next_screen=5 if adaptive else 12
        screen_pending=False
        previous_image=None; stable_frames=0; route_index=0; last_key=0
        def take_screen():
            nonlocal previous_image,stable_frames,route_index,last_key,next_screen,screen_pending
            from PIL import ImageChops
            now=time.monotonic()-started
            tag=f'screen-{round(now):03d}'
            rendered=s.screen(tag)
            if not rendered and adaptive and route_index==0:
                # The initial keyboard/mouse prompt uses VGA text mode.
                if s.key('space'):
                    route_index=1; last_key=now
            if rendered and adaptive:
                current=s.last_image
                if previous_image is not None:
                    delta=ImageChops.difference(current.convert('L'),previous_image.convert('L'))
                    changed=sum(delta.point(lambda v:255 if v>8 else 0).histogram()[128:])
                    stable_frames=stable_frames+1 if changed<200 else 0
                previous_image=current.copy()
                if stable_frames>=1 and now-last_key>=1.5:
                    key=route[route_index] if route_index<len(route) else 'enter'
                    if s.key(key):
                        route_index+=1; last_key=now; stable_frames=0
                        print(json.dumps(dict(scenario=scenario,key_index=route_index,key=key,frame=tag)),flush=True)
            s.call('EXEC RUN'); screen_pending=False
            next_screen=time.monotonic()-started+(1 if adaptive else 25)
        last_event=started
        while time.monotonic()-started<seconds:
            if time.monotonic()-last_progress>=20:
                print(json.dumps(dict(scenario=scenario,events=count,elapsed_s=round(time.monotonic()-started))),flush=True)
                last_progress=time.monotonic()
            if (Path(out)/'stop').exists(): break
            if time.monotonic()-started>=next_screen and not screen_pending and time.monotonic()-last_event>2:
                s.call('BREAK')
                screen_pending=True
                time.sleep(.05)
            r=s.regs()
            ah=r['AX']>>8
            site=(r['CS'],r['IP'])
            # BPINT stops before CD21; a running CPU is not an event.
            if ah not in (0x3d,0x3e,0x3f,0x42):
                if screen_pending and s.regs()==r:
                    take_screen()
                time.sleep(.03); continue
            if site not in sites:
                code=s.dump(*site,2)
                sites[site]=code==b'\xcd\x21'
            if not sites[site]:
                if screen_pending and s.regs()==r:
                    take_screen()
                time.sleep(.03); continue
            # Confirm an actual stable stop (avoid mistaking a sampled CPU).
            if s.regs()!=r: continue
            op={0x3d:'open',0x3e:'close',0x3f:'read',0x42:'seek'}[ah]
            handle=r['BX'] if op!='open' else None
            state=handles.get(handle,{})
            event=dict(seq=count, scenario_downs=scenario, op=op,
                name=state.get('name'),handle=handle,offset=state.get('position'),
                requested=r['CX'] if op=='read' else None,
                caller=f'{r["CS"]:04X}:{r["IP"]:04X}',
                caller_image_offset=r['CS']*16+r['IP']-entry['CS']*16,
                input=r, elapsed_s=round(time.monotonic()-started,3))
            if op=='open':
                raw=s.dump(r['DS'],r['DX'],min(260,65536-r['DX']))
                if b'\0' not in raw: raise RuntimeError('Unterminated DOS path')
                event['name']=raw.split(b'\0')[0].decode('cp437')
                event['open_mode']=r['AX']&255
            if op=='seek':
                event['whence']=r['AX']&255
                displacement=(r['CX']<<16)|r['DX']
                event['displacement']=displacement-(1<<32) if displacement&0x80000000 else displacement
            ret=(r['CS'],(r['IP']+2)&65535)
            s.call(f'EXEC BP {ret[0]:04X}:{ret[1]:04X}')
            s.call('EXEC RUN')
            deadline=time.monotonic()+5
            previous_return=None
            while True:
                rr=s.regs()
                if (rr['CS'],rr['IP'])==ret: break
                if rr==previous_return:
                    # VRT can interrupt a native DOS callback before INT21
                    # returns. Continue to the already armed return BP.
                    s.call('EXEC RUN')
                previous_return=rr
                if time.monotonic()>deadline: raise RuntimeError('INT21 return timeout')
                time.sleep(.002)
            event.update(ax=rr['AX'],cf=rr['CF'],output=rr)
            s.call('EXEC BPDEL 0')
            if not rr['CF']:
                if op=='open':
                    event.update(handle=rr['AX'],offset=0)
                    handles[rr['AX']]={'name':event['name'],'position':0}
                elif op=='seek':
                    event['result_offset']=(rr['DX']<<16)|rr['AX']
                    if handle in handles: handles[handle]['position']=event['result_offset']
                elif op=='read':
                    n=rr['AX']; event['size']=n
                    if n:
                        data=s.dump(r['DS'],r['DX'],n)
                        event['buffer_sha256']=hashlib.sha256(data).hexdigest()
                        name=event['name']
                        path=GAME/(name.replace('\\','/').split('/')[-1].lower()) if name else None
                        if path and path.is_file() and event['offset'] is not None:
                            source=path.read_bytes()
                            event['source_sha256']=hashlib.sha256(source).hexdigest()
                            event['buffer_equals_file_slice']=data==source[event['offset']:event['offset']+n]
                            summary['read_mismatches']+=not event['buffer_equals_file_slice']
                    if handle in handles: handles[handle]['position']+=n
                elif op=='close': handles.pop(handle,None)
            log.write(json.dumps(event,ensure_ascii=False)+'\n'); log.flush()
            count+=1; last_event=time.monotonic()
            s.call('EXEC RUN')
            if time.monotonic()-last_progress>=20:
                print(json.dumps(dict(scenario=scenario,events=count,elapsed_s=round(last_event-started))),flush=True)
                last_progress=last_event
        summary.update(events=count,elapsed_s=round(time.monotonic()-started),complete=not (Path(out)/'stop').exists(),
                       endpoint_scope='bounded capture; inspect VGA frames to establish game state',
                       stopped_by_marker=(Path(out)/'stop').exists(),open_handles=handles)
    (Path(out)/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(finished=scenario,**summary,out=str(out))),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--probe',action='store_true')
    ap.add_argument('--scenario',type=int,choices=range(6))
    ap.add_argument('--all',action='store_true',help='Run all six scenarios sequentially')
    ap.add_argument('--seconds',type=int,default=150)
    ap.add_argument('--menu',action='store_true')
    ap.add_argument('--keys',help='Override AUTOTYPE route, e.g. "space enter down enter enter"')
    ap.add_argument('--adaptive',action='store_true',help='Wait for stable VGA frames, supply guest BIOS keys')
    ap.add_argument('--out', type=Path, default=ROOT/'artifacts/experiments'/datetime.now(timezone.utc).strftime('IOLOG-%Y%m%dT%H%M%SZ'))
    args=ap.parse_args()
    if args.probe: probe(args.out)
    elif args.scenario is not None: capture(args.out,args.scenario,args.seconds,args.menu,args.keys,args.adaptive)
    elif args.all:
        for scenario in range(6): capture(args.out/f'scenario-{scenario}',scenario,args.seconds,args.menu,args.keys,args.adaptive)
    else: ap.error('Choose --probe, --scenario N, or --all')
