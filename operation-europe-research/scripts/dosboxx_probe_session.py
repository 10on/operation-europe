"""TASK-010 bounded interactive native debugger session; JSON command stdin.

Game input is supplied by DOSBox-X AUTOTYPE; debugger uses loopback API.
Never run the DOS executable on the host; only DOSBox-X receives it.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DOWNS = 1 if '--next-scenario' in sys.argv else 0
if '--scenario-downs' in sys.argv:
    SCENARIO_DOWNS=int(sys.argv[sys.argv.index('--scenario-downs')+1])
    if not 2<=SCENARIO_DOWNS<=5: raise ValueError('Explicit scenario down count must be 2..5; use default/--next-scenario for 0/1')
EXPERIMENT = 'TASK-011' if '--slice-reader' in sys.argv else 'TASK-010'
if '--helper-diff' in sys.argv: EXPERIMENT='TASK-012'
if '--next-scenario' in sys.argv: EXPERIMENT='TASK-013' if '--helper-diff' in sys.argv else 'TASK-014'
if '--scenario-downs' in sys.argv:
    if '--slice-reader' in sys.argv or '--helper-diff' in sys.argv: raise ValueError('Explicit down-count mode captures read pairs only')
    EXPERIMENT=f'TASK-{13+SCENARIO_DOWNS:03}'
if '--slice-caller' in sys.argv: EXPERIMENT='TASK-019'
if '--text-chain' in sys.argv: EXPERIMENT='TASK-021'
OUT = ROOT / 'artifacts/experiments' / EXPERIMENT / datetime.now(timezone.utc).strftime('run-%Y%m%dT%H%M%SZ')
PRIVATE = ROOT / 'private'
GAME = PRIVATE / 'game-dos-working/main.exe'
OUT.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('native_probe', ROOT/'artifacts/experiments/TASK-008/probe_debugger.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def main():
    before = hashlib.sha256(GAME.read_bytes()).hexdigest()
    if before != '0b33be2fd37b965e5b92d1881f34226c1608eff6d0358787a7cb5049f218e9df':
        raise ValueError('Working EXE differs from expected version')
    config=(ROOT/'artifacts/experiments/TASK-008/dosboxx-task008.conf').read_text(encoding='utf-8')
    config=config.replace('TASK-008','TASK-010').replace('58991','58992')
    if '--headless' in sys.argv:
        config=config.replace('[sdl]', '[sdl]\nvideodriver=dummy')
    if '--autotype' in sys.argv:
        keys='space enter '+('down '*SCENARIO_DOWNS)+'enter enter'
        config=config.replace('DEBUGBOX MAIN', 'AUTOTYPE -w 5 -p 3 '+keys+'\nDEBUGBOX MAIN')
    config_path=PRIVATE/'dosboxx-task010.conf'
    config_path.write_text(config,encoding='utf-8')
    (OUT/'config.conf').write_text(config,encoding='utf-8')
    records=[]
    with socket.socket() as server:
        server.bind(('127.0.0.1',58992)); server.listen(1); server.settimeout(25)
        env=os.environ.copy(); env.pop('SDL_VIDEODRIVER',None)
        if '--headless' in sys.argv: env['SDL_VIDEODRIVER']='dummy'
        startup=subprocess.STARTUPINFO(); startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow=5
        with (OUT/'emulator.log').open('w',encoding='utf-8') as log:
            proc=subprocess.Popen([r'C:\DOSBox-X\dosbox-x.exe','-conf',config_path.name,'-fastlaunch','-nopromptfolder'],
                                  cwd=PRIVATE,env=env,startupinfo=startup,
                                  creationflags=subprocess.CREATE_NEW_CONSOLE if '--new-console' in sys.argv else 0,
                                  stdout=None if '--new-console' in sys.argv else log,
                                  stderr=None if '--new-console' in sys.argv else log)
            timer=threading.Timer(1200,proc.terminate); timer.daemon=True; timer.start()
            try:
                conn,peer=server.accept()
                if peer[0]!='127.0.0.1': raise RuntimeError('Non-loopback peer')
                with conn:
                    ctl=native.Control(conn)
                    print(json.dumps({'ready':True,'pid':proc.pid,'peer':peer[0],'max_seconds':1200}),flush=True)
                    if '--auto' in sys.argv:
                        auto_probe(ctl, records)
                        return
                    while proc.poll() is None:
                        text=input()
                        if text.strip()=='QUIT': break
                        command=json.loads(text)['command']
                        if not (command=='PING' or command.startswith(('EXEC EV ','EXEC BP ','EXEC BPINT ','EXEC MEMDUMPBIN ','EXEC RUN','EXEC BPLIST','EXEC BPDEL '))):
                            raise ValueError('Command outside bounded debugger allowlist')
                        start=time.monotonic()
                        try:
                            result=ctl.call(command,timeout=15)
                        except (ConnectionError,OSError) as exc:
                            records.append({'command':command,'error':type(exc).__name__,'process_exit':proc.poll()})
                            (OUT/'commands.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
                            if proc.poll() is not None or not (command=='PING' or command.startswith('EXEC EV ')):
                                raise
                            conn.close()
                            conn,peer=server.accept()
                            if peer[0]!='127.0.0.1': raise RuntimeError('Non-loopback reconnect')
                            ctl=native.Control(conn)
                            result=ctl.call(command,timeout=15)
                        result['elapsed_ms']=round((time.monotonic()-start)*1000)
                        records.append(result)
                        (OUT/'commands.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
                        print(json.dumps(result),flush=True)
            finally:
                timer.cancel()
                if proc.poll() is None: proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill();proc.wait(timeout=5)
                after=hashlib.sha256(GAME.read_bytes()).hexdigest()
                (OUT/'session.json').write_text(json.dumps({'before':before,'after':after,'unchanged':before==after,'pid':proc.pid,'command_count':len(records)},indent=2),encoding='utf-8')


def auto_probe(ctl, records):
    def call(command):
        result=ctl.call(command,timeout=10)
        records.append(result)
        (OUT/'commands.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
        if result['status']!='OK': raise RuntimeError('Debugger rejected command')
        return result
    def regs():
        result=call('EXEC EV CS IP DS SS SP AX BX CX DX')
        values=result['lines'][-1].split()
        if len(values)!=9: raise ValueError('Unexpected register response')
        return dict(zip(['CS','IP','DS','SS','SP','AX','BX','CX','DX'],[int(x,16) for x in values]))
    time.sleep(2)
    entry=regs()
    if entry['IP']!=0x409C: raise RuntimeError('Not at verified MZ entry')
    base=entry['CS']
    points = {0x7144:('scedata',0x2E8C,16), 0x714D:('scedata-open',None,0),
              0x716C:('scedata-read',0x42,8143), 0x7180:('mapinf',0x2EF2,16),
              0x7189:('mapinf-open',None,0), 0x71B7:('mapinf-read',0x20B6,1600)}
    slice_mode='--slice-reader' in sys.argv
    buffer_ptr=None
    if slice_mode:
        points={0x71C6:('slice-entry',None,0),0x71E4:('slice-name',0x2E8C,16),
                0x71ED:('slice-open',None,0),0x71F6:('slice-seek',None,0),
                0x7208:('slice-read',None,800)}
    if '--helper-diff' in sys.argv:
        points={0x716C:('helper-before',0x42,8143),0x7180:('helper-after',0x42,8143)}
    if '--slice-caller' in sys.argv: points={0x71C6:('slice-caller',None,0)}
    text_chain='--text-chain' in sys.argv
    if text_chain: points={0x7208:('text-source',None,800),0x8472:('text-wrapper',None,800),0x4C84:('text-consumer',None,800)}
    for offset in ([0x7208] if text_chain else points): call(f'EXEC BP {base:04X}:{offset:04X}')
    call('EXEC RUN')
    hits=[]
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        time.sleep(2)
        current=regs(); linear=current['CS']*16+current['IP']
        offset=linear-base*16
        if offset in points:
            tag,ptr,size=points[offset]
            if tag=='text-source': ptr=current['DX']
            if tag in ('text-wrapper','text-consumer'): ptr=current['BX']
            if tag=='slice-entry': buffer_ptr=current['BX']
            if tag=='slice-read':
                if buffer_ptr is None: raise RuntimeError('Missing entry buffer pointer')
                ptr=buffer_ptr
            hit={'tag':tag,'registers':current,'load_base':base,'image_offset':hex(offset)}
            if tag=='slice-caller':
                stackfile='T019-'+OUT.name[-7:-1]+'.bin'
                call(f'EXEC MEMDUMPBIN {current["SS"]:04X}:{current["SP"]:04X} 0010 {stackfile}')
                stack=(PRIVATE/stackfile).read_bytes()
                (OUT/'entry-stack.bin').write_bytes(stack)
                hit['stack_sha256']=hashlib.sha256(stack).hexdigest()
            filename='T010-'+OUT.name[-7:-1]+'-'+tag+'.bin'
            if ptr is not None:
                call(f'EXEC MEMDUMPBIN {current["DS"]:04X}:{ptr:04X} {size:04X} {filename}')
            path=PRIVATE/filename
            if ptr is not None and path.exists():
                raw=path.read_bytes(); (OUT/(tag+'-name.bin')).write_bytes(raw)
                hit['name_hex']=raw[:16].hex();hit['name_sha256']=hashlib.sha256(raw).hexdigest()
                hit['dump_size']=len(raw)
                if tag.endswith('-read'):
                    source=GAME.parent/('scedata' if tag in ('scedata-read','slice-read') else 'mapinf.dat')
                    data=source.read_bytes()
                    starts=range(9600,len(data)-size+1,size) if tag=='scedata-read' else range(0,len(data)-size+1,size)
                    hit['matching_file_offsets']=[n for n in starts if data[n:n+size]==raw]
                    hit['source_sha256']=hashlib.sha256(data).hexdigest()
            hits.append(hit)
            (OUT/'hits.json').write_text(json.dumps(hits,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'hit':tag,'registers':current,'name_hex':hit.get('name_hex')}),flush=True)
            if tag in ('mapinf-read','slice-read','helper-after','slice-caller','text-consumer'): break
            if tag=='text-source': call(f'EXEC BP {base:04X}:8472')
            if tag=='text-wrapper': call(f'EXEC BP {base:04X}:4C84')
            call('EXEC RUN')
    (OUT/'result.json').write_text(json.dumps({'entry':entry,'hits':hits,'timed_out':len(hits)<len(points)},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'finished':True,'hits':len(hits),'evidence':str(OUT)}),flush=True)


if __name__=='__main__':
    main()
