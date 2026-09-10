"""Curate local evidence, preserving raw hashes and explicit redaction."""
from pathlib import Path
import hashlib, json, re, shutil
import sys
HERE=Path(__file__).resolve().parent
STUDIO=HERE.parents[2]/"studio"
local=json.loads((HERE/"partial-run.local.json").read_text())
root=Path(local["output"])
evidence=json.loads((root/"evidence.json").read_text(encoding="utf-8"))
assert evidence["status"]=="PARTIAL_RUNTIME_PASS" and evidence["source_unchanged"]
target=STUDIO/"evidence"/("gt01-partial-"+local["run_id"])
if target.exists():
    if "--refresh-unpublished" not in sys.argv:
        raise FileExistsError("use fresh run or explicitly refresh this unreviewed package")
    old=json.loads((target/"package.json").read_text())
    assert old["run_id"]==local["run_id"] and old["proof_class"]=="PARTIAL_RUNTIME_NOT_ACCEPTANCE"
else:
    target.mkdir(parents=True,exist_ok=False)
rows=[]
for file in sorted(root.iterdir()):
    if file.suffix not in {".json",".txt"} or not file.is_file():continue
    raw=file.read_bytes()
    text=raw.decode("utf-8",errors="strict")
    clean=re.sub(r"""(?<![A-Za-z0-9])[A-Za-z]:[\\/][^"'\r\n]*""","<LOCAL_PATH>",text)
    clean=clean.replace("\r\n","\n")
    clean=(clean.rstrip()+"\n") if clean.strip() else ""
    (target/file.name).write_text(clean,encoding="utf-8",newline="\n")
    rows.append({"path":file.name,"raw_sha256":hashlib.sha256(raw).hexdigest(),
                 "sha256":hashlib.sha256((target/file.name).read_bytes()).hexdigest(),
                 "redacted":clean!=text})
image=root/"snapshot/menu.png"
shutil.copyfile(image,target/"menu.png")
rows.append({"path":"menu.png","sha256":hashlib.sha256(image.read_bytes()).hexdigest(),"redacted":False})
(target/"package.json").write_text(json.dumps({"schema":"hh-partial-evidence-package-v1",
   "run_id":local["run_id"],"proof_class":"PARTIAL_RUNTIME_NOT_ACCEPTANCE",
   "artifacts":rows,"raw_location":"Recorded in ignored review partial-run.local.json",
   "redaction":"Absolute local paths replaced; CRLF normalized and terminal whitespace trimmed. Raw hashes retained; no exit/trace semantics changed."},
   indent=2)+"\n",encoding="utf-8",newline="\n")
(HERE/"partial-package.json").write_text(json.dumps({"path":target.relative_to(STUDIO).as_posix(),
    "package_sha256":hashlib.sha256((target/"package.json").read_bytes()).hexdigest()},indent=2)+"\n",encoding="utf-8",newline="\n")
print(target.as_posix())
