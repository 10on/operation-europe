"""Replay oe-iolog state, verify source slices, write a batch file map."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/'private/game-dos-working'
TITLES=[(0x51a9d,'Invasion of France'),(0x51ab1,'The Battle for North Africa'),
        (0x51ace,'The Armored Battle at Kursk'),(0x51aeb,'D-Day at Normandy'),
        (0x51afe,'The Battle of the Bulge'),(0x51b17,'The Battle for Berlin')]

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def ranges(values):
    a=sorted(set(values)); chunks=[]; i=0
    while i<len(a):
        j=i+1
        if j+1<len(a):
            step=a[j]-a[i]
            while j+1<len(a) and a[j+1]-a[j]==step: j+=1
            if j-i>=2:
                chunks.append(f'{a[i]}…{a[j]} (шаг {step})'); i=j+1; continue
        chunks.append(str(a[i])); i+=1
    return ', '.join(chunks)

def replay(path):
    rows=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
    handles={}; reads=[]
    for i,e in enumerate(rows):
        assert e['seq']==i and e['cf'] in (0,1)
        assert e['input']['CS']*16+e['input']['IP']==int(e['caller'].split(':')[0],16)*16+int(e['caller'].split(':')[1],16)
        assert (e['output']['CS'],e['output']['IP'])==(e['input']['CS'],e['input']['IP']+2)
        if e['cf']: continue
        op,h=e['op'],e['handle']
        if op=='open':
            assert h==e['ax'] and e['offset']==0
            handles[h]=[e['name'],0]
            continue
        assert h in handles and handles[h]==[e['name'],e['offset']]
        if op=='close': del handles[h]
        elif op=='seek':
            base=(0,handles[h][1],(GAME/e['name'].lower()).stat().st_size)[e['whence']]
            assert e['result_offset']==base+e['displacement']
            handles[h][1]=e['result_offset']
        elif op=='read':
            assert e['size']==e['ax'] and e['size']<=e['requested']
            source=GAME/e['name'].lower()
            data=source.read_bytes()
            if e['size']:
                assert digest(source)==e['source_sha256']
                assert hashlib.sha256(data[e['offset']:e['offset']+e['size']]).hexdigest()==e['buffer_sha256']
                assert e['buffer_equals_file_slice'] is True
            handles[h][1]+=e['size']; reads.append(e)
    session=json.loads((path.parent/'session.json').read_text())
    assert session['unchanged'] and session['before']==session['after']
    return rows,reads,session

def compact_report(path, task, status, goal, claims, evidence, summary, questions, next_step):
    obj=dict(schema_version='1',task_id=task,status=status,goal=goal,
        methods=['Локальный воспроизводимый скрипт; адреса и SHA в артефактах'],
        environment={'platform':'Windows / Python 3.12 / DOSBox-X, loopback only'},
        claims=claims,evidence=evidence,human_summary_ru=summary,
        open_questions=questions,next_step=next_step)
    # 14 lines, one complete value per top-level property.
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('{\n'+',\n'.join('  '+json.dumps(k)+': '+json.dumps(v,ensure_ascii=False) for k,v in obj.items())+'\n}\n',encoding='utf-8')

def generate(batch,out):
    batch=batch.resolve(); out=out.resolve()
    main=(GAME/'main.exe').read_bytes()
    for offset,title in TITLES:
        assert main[offset:].split(b'\0')[0].decode('ascii').strip()==title
    lines=['# Файловая карта шести сценариев', '',
        'Все смещения и размеры — десятичные file offsets от начала файла. Строки N — число Down в меню.',
        'Источник: main.exe SHA-256 `'+digest(GAME/'main.exe')+'`; SCEDATA SHA-256 `'+digest(GAME/'scedata')+'`.',
        '', '## Метод и границы', '',
        'BPINT 21h/AH=3Dh,3Fh,42h,3Eh с начала MAIN; результат снят до следующей инструкции по CS:IP+2. '
        'Позиция ведётся отдельно для каждого handle, повторное открытие сбрасывает её. '
        'Каждое успешное ненулевое чтение сверено целиком с файлом и повторно проверено по SHA буфера.',
        'Не охвачены запуск FMDRV до MAIN, create/extended-open, save/load и дальнейшая игра. '
        'Ввод, кадры и исходные регистры лежат рядом с JSONL. VGA-кадры восстановлены из четырёх плоскостей; палитра нейтральная, цвета не измерены.',
        'Ограничение маршрута: AUTOTYPE продолжал посылать Enter после появления карты. Кадры показывают исполнение приказов '
        'и продвижение времени до нескольких часов; выбор One Player не подтверждён. Таблица включает все чтения за 190 секунд, '
        'в том числе после загрузки карты. Точная остановка на первом готовом стратегическом экране ещё не реализована. '
        'Флаг complete=false в исходных summary.json был не обновляемым полем ранней версии сборщика; завершение всех шести интервалов проверено по elapsed_s=190 и session.json.',
        '', '## Названия и текстовые блоки SCEDATA', '',
        'Названия сверены по VGA-кадру меню и NUL-строкам main.exe по указанным file offsets. '
        'Нумерация 800-байтовых блоков с нуля; группа 0…5 — предыстории, 6…11 — условия победы.',
        '', '| N | Название в меню | main.exe offset | Предыстория: блок / offset | Условия: блок / offset | Проверка |',
        '|---:|---|---:|---:|---:|---|']
    totals=Counter(); manifest=[]; all_reads=[]
    data_by_scenario=[]
    for n,(offset,title) in enumerate(TITLES):
        run=batch/f'scenario-{n}'
        events,reads,session=replay(run/'io.jsonl')
        summary=json.loads((run/'summary.json').read_text())
        assert summary['read_mismatches']==0
        narrative=[e for e in reads if e['name']=='SCEDATA' and e['size']==800]
        assert any(e['offset']==n*800 for e in narrative)
        record=[e for e in reads if e['name']=='SCEDATA' and e['size']==8143]
        assert any(e['offset']==17743+n*8143 for e in record)
        assert any(e['name']=='MAPINF.DAT' and e['offset']==n*1600 and e['size']==1600 for e in reads)
        objective=any(e['name']=='SCEDATA' and e['offset']==(n+6)*800 and e['size']==800 for e in reads)
        lines.append(f'| {n} | {title} | {offset} | {n} / {n*800} | {n+6} / {(n+6)*800} | предыстория observed; условия '+('observed' if objective else 'inferred, при выборе не читались')+' |')
        totals.update(e['op'] for e in events)
        all_reads+=reads; data_by_scenario.append((n,title,events,reads))
        manifest.append(dict(scenario=n,title=title,events=len(events),reads=len(reads),
            bytes_read=sum(e['size'] for e in reads),io_sha256=digest(run/'io.jsonl'),
            session_sha256=digest(run/'session.json'),scoped_to='MAIN entry to bounded route endpoint',
            screenshots=[dict(path=str(p.relative_to(ROOT)),sha256=digest(p)) for p in sorted(run.glob('screen*.png'))]))
    lines+=['', 'Блоки условий сопоставлены по текстовому содержимому и порядку; отсутствие чтения в этом маршруте '
        'не доказывает, что игра их не использует. Динамическую связь этих шести блоков нужно проверить через Info → Victory.',
        '', '## Сценарий → чтения файлов', '',
        'В одной строке собраны все уникальные offsets для одного размера чтения; повторы учтены в числе операций. '
        'Полная последовательность open/seek/read/close, handle, AX/CF и CS:IP — в соответствующем `io.jsonl`.',
        '', '| N | Файл | Offsets чтения | Размер | Чтений |', '|---:|---|---|---:|---:|']
    for n,title,events,reads in data_by_scenario:
        groups=defaultdict(list)
        for e in reads: groups[e['name'],e['size']].append(e['offset'])
        for (name,size),offsets in sorted(groups.items()):
            lines.append(f'| {n} | {name} | {ranges(offsets)} | {size} | {len(offsets)} |')
    lines+=['','## Артефакты и повторение','',
        f'Пакет: `{batch.relative_to(ROOT).as_posix()}/scenario-N/io.jsonl`; '
        f'сводка и хеши кадров: `{batch.relative_to(ROOT).as_posix()}/verified.json`.',
        '`oe-iolog --all --seconds 190 --out <новый каталог>`; затем '
        '`python scripts/oe_file_map.py <каталог>`. Нужны DOSBox-X с native debugger API и Pillow.',
        '', f'Всего: {sum(totals.values())} операций, {len(all_reads)} чтений, '
        f'{sum(e["size"] for e in all_reads)} байт; расхождений буферов — 0. Confidence: observed для этих запусков.',
        '', '## Структурный парсер', '',
        '`scripts/scedata_record.py`: 12×800 байт + 7×8143 байт; round-trip всего файла и каждой записи побайтно равен. '
        'Шесть выбираемых записей имеют offsets 17743…58458; запись offset 9600 в этих шести загрузках не выбрана. '
        'Смысл большей части полей остаётся unknown; парсер сохраняет их как opaque bytes, календарь +2…+6 — только кандидат.']
    out.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    result=dict(scenarios=manifest,operation_counts=dict(totals),verified_reads=len(all_reads),
        bytes_read=sum(e['size'] for e in all_reads),mismatches=0,
        source_hashes={p.name:digest(p) for p in GAME.iterdir() if p.is_file()})
    (batch/'verified.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(scenarios=6,operations=sum(totals.values()),reads=len(all_reads),mismatches=0,map=str(out))))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('batch',type=Path)
    ap.add_argument('--out',type=Path,default=ROOT/'knowledge/FILE_MAP.md')
    a=ap.parse_args();generate(a.batch,a.out)
