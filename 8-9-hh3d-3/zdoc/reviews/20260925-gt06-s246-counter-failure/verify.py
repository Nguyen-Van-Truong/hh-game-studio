from pathlib import Path
import hashlib,json,zipfile
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3]; RAW=ROOT/"8-9-hh3d-3/studio/.local/reviews/gt06-s246-formal-01"; SUP=ROOT/"8-9-hh3d-3/studio/.local/reviews/gt06-s246-formal-01-supervisor"; ARCH=ROOT/"8-9-hh3d-3/studio/.local/archives/gt06-s246-formal-01-s247-counter-failure.zip"
def sha(b): return hashlib.sha256(b).hexdigest()
def need(x,m):
 if not x: raise ValueError(m)
def main():
 a=json.loads((HERE/"analysis.json").read_bytes()); need(a["authority"]==0 and not a["formal_acceptance"],"scope")
 man=(RAW/"raw-manifest.json").read_bytes(); need(sha(man)==a["raw_manifest_sha256"],"raw manifest")
 m=json.loads(man); entries=m["entries"]; need(len(entries)==a["raw_files"],"entry count"); names=set()
 for e in entries:
  p=e["path"]; need(p not in names and (p.startswith("raw/") or p.startswith("supervisor/")),p); names.add(p); base=RAW if p.startswith("raw/") else SUP; b=(base/p.split("/",1)[1]).read_bytes(); need(len(b)==e["bytes"] and sha(b)==e["sha256"],p)
 with zipfile.ZipFile(ARCH) as z:
  need(sha(ARCH.read_bytes())==a["archive_sha256"],"archive sha"); need(set(z.namelist())==names|{"raw-manifest.json"},"members"); need(z.read("raw-manifest.json")==man,"manifest archive")
  for p in names:
   base=RAW if p.startswith("raw/") else SUP; need(z.read(p)==(base/p.split("/",1)[1]).read_bytes(),p)
 f=json.loads((RAW/"run-00-attempt-01/child-failure.json").read_bytes()); c=json.loads((RAW/"run-00-attempt-01/child-terminal-cleanup.json").read_bytes()); need(f["code"]==a["terminal_reason"] and f["completed_batches"]==8 and f["phase"]["batch"]==7,"failure"); need(c["observations"]["import_target"]["actual_target_exit"]["exit_code"]==0,"import exit"); need(c["observations"]["editor_owner"]["job"]["zero_observed"] and c["observations"]["editor_owner"]["job"]["closed"] and not c["observations"]["editor_owner"]["job"]["handle_retained"],"cleanup")
 print(json.dumps({"verified":True,"raw_files":len(entries),"archive_members":len(names)+1,"terminal_reason":a["terminal_reason"],"authority":0,"formal_acceptance":False},sort_keys=True))
if __name__=="__main__": main()
