from pathlib import Path
import hashlib,json,zipfile
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3]
RAW=ROOT/"8-9-hh3d-3/studio/.local/reviews/gt06-s245-import-diagnostic-01"
ARCH=ROOT/"8-9-hh3d-3/studio/.local/archives/gt06-s245-import-diagnostic-01-s246-terminal.zip"
def sha(b): return hashlib.sha256(b).hexdigest()
def doc(p): return json.loads(p.read_bytes())
def need(x,m):
    if not x: raise ValueError(m)
def main():
    a=doc(HERE/"analysis.json"); need(a["authority"]==0 and a["formal_acceptance"] is False,"scope")
    man=(RAW/"raw-manifest.json").read_bytes(); need(sha(man)==a["raw_manifest_sha256"],"manifest sha")
    m=json.loads(man); need(len(m["files"])==a["raw_entries"],"rows")
    names=set()
    for row in m["files"]:
        need(row["path"].startswith("raw/"),"path"); need(row["path"] not in names,"duplicate"); names.add(row["path"])
        b=(RAW/row["path"][4:]).read_bytes(); need(len(b)==row["bytes"] and sha(b)==row["sha256"],row["path"])
    actual={"raw/"+p.relative_to(RAW).as_posix() for p in RAW.rglob("*") if p.is_file() and p.name!="raw-manifest.json"}; need(actual==names,"membership")
    arc=ARCH.read_bytes(); need(sha(arc)==a["archive_sha256"],"archive sha")
    with zipfile.ZipFile(ARCH) as z:
        need(len(z.namelist())==a["archive_members"] and len(set(z.namelist()))==len(z.namelist()),"zip count"); need(z.read("raw-manifest.json")==man,"zip manifest")
        for n in names: need(z.read(n)==(RAW/n[4:]).read_bytes(),n)
    c=doc(RAW/"capture.json"); need(c["completed_diagnostic"] and c["formal_acceptance"] is False,"capture")
    need(c["actual_exits"]["import"]["exit_code"]==0 and c["actual_exits"]["editor"]["exit_code"]==0,"exits")
    for job in c["jobs"].values(): need(job["closed"] and job["zero_observed"] and not job["handle_retained"],"job")
    print(json.dumps({"verified":True,"run_id":a["run_id"],"raw_files":len(names),"archive_members":len(zipfile.ZipFile(ARCH).namelist()),"authority":0},sort_keys=True))
if __name__=="__main__": main()
