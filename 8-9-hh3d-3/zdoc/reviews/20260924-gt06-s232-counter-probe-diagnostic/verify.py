"""Engine-free verifier for the S232 bounded diagnostic packet."""
from __future__ import annotations
import hashlib, json, pathlib, zipfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RAW = ROOT / "8-9-hh3d-3/studio/.local/reviews/gt06-s232-counter-probe-syntax-02"
ARCHIVE = ROOT / "8-9-hh3d-3/studio/.local/archives/gt06-s232-counter-probe-syntax-02-s233-terminal.zip"
ANALYSIS = json.loads((HERE / "analysis.json").read_text(encoding="utf-8"))

def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

assert ANALYSIS["authority"] == 0 and ANALYSIS["formal_acceptance"] is False
assert ANALYSIS["source_files"] == 53
assert ANALYSIS["editor_actual_exit"] == 0 and ANALYSIS["import_actual_exit"] == 0
assert ANALYSIS["editor_job_zero_closed"] and ANALYSIS["import_job_zero_closed"]
assert ANALYSIS["editor_handles_released"] and ANALYSIS["import_handles_released"]
assert ANALYSIS["host_integrated"] is False and ANALYSIS["post_ack_probe_exercised"] is False
assert sha(RAW / "raw-manifest.json") == ANALYSIS["raw_manifest_sha256"]
assert sha(ARCHIVE) == ANALYSIS["archive_sha256"]
with zipfile.ZipFile(ARCHIVE) as archive:
    assert len(archive.namelist()) == ANALYSIS["archive_members"]
    assert archive.namelist()[0] == "raw-manifest.json"
print(json.dumps({"run_id": ANALYSIS["run_id"], "verified_files": ANALYSIS["verified_files"],
                  "formal_acceptance": False, "authority": 0}, sort_keys=True))
