from pathlib import Path
import hashlib, json
ROOT=Path(__file__).resolve().parents[3]
Z=ROOT/'zdoc'
T=Z/'8-9-godot-blender-agent-studio-plan.txt'
G=Z/'8-9-hh-world-gameplay-viet-nam-plan.txt'
s=T.read_text(encoding='utf-8')
s=s.replace('Godot 4.7.2-stable standard\n+ matching export templates', 'Godot 4.7.2-stable standard, matching export templates')
if s==T.read_text(encoding='utf-8'): raise SystemExit('tool plus anchor absent')
T.write_text(s,encoding='utf-8',newline='\n')
files=[]
for p in (T,G):
    b=p.read_bytes(); files.append({'path':p.name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
m={'revision':'S4','proof_class':'PLAN_DESIGN','files':files}
m['manifest_sha256']=hashlib.sha256('\n'.join(f"{x['path']} {x['sha256']}" for x in sorted(files,key=lambda x:x['path'])).encode()).hexdigest()
(ROOT/'zdoc/reviews/20260908-r3/freeze-s4.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(m,ensure_ascii=True,indent=2))
