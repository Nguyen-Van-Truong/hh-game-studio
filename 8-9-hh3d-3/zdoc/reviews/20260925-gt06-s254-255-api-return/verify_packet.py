from pathlib import Path
import hashlib,json
p=Path(__file__).parent
m=json.loads((p/"packet-manifest.json").read_text())
for n,d in m["files"].items():
 if n=="packet-manifest.json": continue
 h=hashlib.sha256((p/n).read_bytes()).hexdigest()
 assert h==d,(n,h,d)
rm=json.loads((p/"raw-manifest.json").read_text())
root=p.parents[2]/"studio/.local/reviews"
for rel,meta in rm["entries"].items():
 q=root/rel
 assert q.is_file() and q.stat().st_size==meta["bytes"],rel
 assert hashlib.sha256(q.read_bytes()).hexdigest()==meta["sha256"],rel
a=json.loads((p/"analysis.json").read_text())
assert a["authority"]==0 and a["formal_acceptance"] is False
assert a["fixture"]["target_exit"]==0 and a["fixture"]["cdb_exit"]==0
assert len(a["fixture"]["return_rows"])==2
assert a["godot"]["observations"] and all(x["cleanup"]["job"]["closed"] for x in a["godot"]["observations"])
print("S254_S255_PACKET_VERIFY_PASS")
