"""Check that the Git index contains the exact evidenced source and artifacts."""
from pathlib import Path
import hashlib, json, re, subprocess
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
STUDIO_PREFIX="8-9-hh3d-3/studio/"
REVIEW_PREFIX="8-9-hh3d-3/zdoc/reviews/20260910-r6/"

def staged(path):
    return subprocess.check_output(["git","show",":"+path],cwd=REPO)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

manifest=json.loads(staged(REVIEW_PREFIX+"freeze-s18.json"))
for row in manifest["files"]:
    assert sha(staged("8-9-hh3d-3/zdoc/"+row["path"]))==row["sha256"]
pointer=json.loads(staged(REVIEW_PREFIX+"partial-package.json"))
package_prefix=STUDIO_PREFIX+pointer["path"]+"/"
package_bytes=staged(package_prefix+"package.json")
assert sha(package_bytes)==pointer["package_sha256"]
package=json.loads(package_bytes)
for artifact in package["artifacts"]:
    assert sha(staged(package_prefix+artifact["path"]))==artifact["sha256"],artifact["path"]
evidence=json.loads(staged(package_prefix+"evidence.json"))
for path,digest in evidence["source_manifest"].items():
    assert sha(staged(STUDIO_PREFIX+path))==digest,path
assert evidence["status"]=="PARTIAL_RUNTIME_PASS"
assert len(evidence["runs"])==9 and all(row["check_pass"] for row in evidence["runs"])
assert evidence["source_unchanged"] and evidence["snapshot_matches"]
reviews=json.loads(staged(REVIEW_PREFIX+"worker-review.json"))
for worker in reviews["workers"]:
    assert sha(staged(REVIEW_PREFIX+"worker-output/"+worker["role"]+".txt"))==worker["sha256"]
rows=subprocess.check_output(["git","diff","--cached","--name-only","--diff-filter=ACM"],cwd=REPO,text=True).splitlines()
sizes=[]
for path in rows:
    raw=staged(path)
    assert len(raw)<90*1024*1024,path
    assert not any(part in path.split("/") for part in [".local",".godot","__pycache__"]),path
    if path.endswith((".txt",".json",".md",".py",".gd")) and path.startswith(STUDIO_PREFIX):
        assert not re.search(rb"(?:[A-Za-z]:[\\/](?:Users|dataDisk)|/Users/)",raw),path
    sizes.append((len(raw),path))
print(json.dumps({"result":"PASS_CHECKPOINT_ONLY","staged_files":len(rows),
                  "largest_blob":max(sizes),"source_files":len(evidence["source_manifest"]),
                  "partial_run":evidence["run_id"],"limits":"No WP/critic/legal acceptance."},indent=2))
