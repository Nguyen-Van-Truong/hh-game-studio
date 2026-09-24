"""Engine-free verifier for the S231 raw-derived boundary packet."""
from __future__ import annotations
import hashlib, json, pathlib, zipfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RAW = ROOT / "8-9-hh3d-3/studio/.local/reviews/gt06-s229-formal-01/run-00-attempt-01"
ANALYSIS = json.loads((HERE / "analysis.json").read_text(encoding="utf-8"))

def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def derive():
    out = []
    for path in sorted(RAW.glob("joint-*.json"), key=lambda p: int(p.stem.split("-")[1])):
        value = json.loads(path.read_text(encoding="utf-8"))
        out.append({
            "batch": value["index"],
            "objects": value["editor"]["native_observation"]["objects"]["value"],
            "resources": value["editor"]["native_observation"]["resources"]["value"],
            "editor_handles": value["editor"]["held_handles"]["value"],
            "host_handles": value["host"]["counters"]["held_handles"]["value"],
            "rss_bytes": value["editor"]["rss_bytes"]["value"],
            "host_effect_count": value["host_effect_count"],
            "status_gap_ms": value["barrier_receipt"]["max_status_gap_ms"],
        })
    return out

assert ANALYSIS["authority"] == 0 and ANALYSIS["formal_acceptance"] is False
assert len(derive()) == 17
assert derive() == ANALYSIS["all_rows"]
rows = derive()
assert rows[4]["objects"] == 71128
assert [(rows[i-1]["batch"], rows[i]["batch"]) for i in range(1, len(rows)) if rows[i]["objects"] != rows[i-1]["objects"]] == [(15, 16)]
assert rows[15]["objects"] == 71128 and rows[16]["objects"] == 71130
assert rows[16]["resources"] == 6 and rows[16]["editor_handles"] == 554 and rows[16]["host_handles"] == 204
assert rows[16]["status_gap_ms"] <= 2000
assert ANALYSIS["decision"].startswith("BOUNDARY_ONLY")
print(json.dumps({"rows": len(rows), "first_object_delta": 2, "authority": 0, "formal_acceptance": False}))
