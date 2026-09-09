from pathlib import Path
import hashlib,json,re,sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[3]; Z=ROOT/'zdoc'; OUT=Path(__file__).resolve().parent
spec=[('8-9-godot-blender-agent-studio-plan.txt',r'GT-\d{2}',10,'TX',14,'TOOLS'),('8-9-hh-world-gameplay-viet-nam-plan.txt',r'H2-P\d-\d{2}',32,'EX',44,'GAME')]
err=[]; stats=[]; ids=[]
for name,pat,want,ep,ew,kind in spec:
 p=Z/name; raw=p.read_bytes(); s=raw.decode('utf-8')
 if '\r' in s or '\x00' in s or '\ufffd' in s: err.append(f'{name}: encoding/control')
 rows=re.findall(rf'(?m)^\d{{2}} \| ({pat}) \| [^\n|]+ \| [^\n|]+ \| PLANNED$',s)
 headings=re.findall(rf'(?m)^### ({pat}) — ',s)
 ex=[int(x) for x in re.findall(rf'(?m)^{ep}(\d{{2}}) — ',s)]
 if len(rows)!=want: err.append(f'{name}: rows={len(rows)} expected={want}')
 if headings!=[f'GT-{i:02}' for i in range(1,11)] if kind=='TOOLS' else headings!=[f'H2-P{p}-{w:02}' for p in range(10) for w in range(1,4) if not (p==0 and w>3) and not (p==1 and w>3) and not (p==2 and w>4) and not (p==3 and w>4) and not (p==4 and w>4) and not (p==5 and w>3) and not (p==6 and w>3) and not (p==7 and w>3) and not (p==8 and w>3) and not (p==9 and w>2)]:
  err.append(f'{name}: heading sequence/count')
 if ex!=list(range(1,ew+1)): err.append(f'{name}: exception sequence')
 cur=re.search(r'(?m)^CURRENT_VALID_WP=(.+)$',s)
 if not cur or not rows or cur.group(1)!=rows[0]: err.append(f'{name}: current WP')
 for marker in ['PLAN_REVISION=S4','EXECUTION_AUTHORIZATION=PLAN_ONLY','IMPLEMENTATION=NOT_STARTED','RUNTIME_ACCEPTANCE=NONE','HUMAN_ACCEPTANCE=NONE',f'END_OF_{kind}_PLAN']:
  if marker not in s: err.append(f'{name}: missing {marker}')
 for i in rows:
  if i in ids: err.append(f'duplicate WP {i}')
  ids.append(i)
 stats.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'rows':len(rows),'exceptions':len(ex)})
if len(ids)!=42: err.append(f'active ids={len(ids)}')
t,g=[(Z/n).read_text(encoding='utf-8') for n,_,_,_,_,_ in spec]
for token in ['GT-10','H2-P0-01','3.2.1 PHẠM VI QUY MÔ','32 người/room','hàng trăm triệu','RSS/heap/GC','cache/CDN','privacy/telemetry profile','16 KB','EX40','EX44']:
 if token not in g: err.append('game missing '+token)
for token in ['studio/fixtures/sample-game','GT-10','canonical wire contract','SSRF','TUF','last-good package','TX18']:
 if token not in t: err.append('tools missing '+token)
if 'GT-10' not in g[:g.find('### H2-P0-02')]: err.append('handoff not at P0-01')
freeze=OUT/'freeze-s4.json'
if not freeze.exists(): err.append('freeze missing')
else:
 m=json.loads(freeze.read_text(encoding='utf-8')); fm={x['path']:x for x in m.get('files',[])}
 for x in stats:
  if fm.get(x['path'],{}).get('sha256')!=x['sha256'] or fm.get(x['path'],{}).get('bytes')!=x['bytes']: err.append('freeze mismatch '+x['path'])
result={'kind':'STATIC_PLAN_CHECK_NOT_RUNTIME','revision':'S4','result':'PASS_STATIC_ONLY' if not err else 'FAIL','plans':stats,'errors':err}
(OUT/'static-s4.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2)); sys.exit(bool(err))
