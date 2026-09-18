"""Reconcile S97 terminal metadata from immutable raw receipts.

The campaign child intentionally leaves self/supervisor exits unknown because
the child cannot observe its own termination.  This verifier reads the outer
actual-exit receipts and emits a derived record; it never changes raw files,
turns a diagnostic into acceptance, or reruns Godot.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[3] / "studio" / ".local" / "reviews" / "gt06-s97-coupled-phases-01"
OUT = Path(__file__).with_name("s97-terminal-exit-reconciliation.json")
RUN = "gt06-s97-coupled-phases-01"
SOURCE = "cfc4b55a5407891bfd54d22d9f1ac45a74b6c744898199a0e4690d6230a6c1d6"
PROFILE = "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85"


def read(rel: str):
    return json.loads((ROOT / rel).read_bytes())


def sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"reconciliation failed: {message}")


child = read("child-result.json")
terminal = read("child-terminal-cleanup.json")
manifest = read("diagnostic-manifest.json")
http = read("http-phases-final.json")
exit_files = {
    "host": read("host-owner/process-exit.json"),
    "editor": read("editor-host/process-exit.json"),
    "import": read("import-host/process-exit.json"),
}
captures = {
    "host": read("host-owner/capture.json"),
    "editor": read("editor-host/capture.json"),
    "import": read("import-host/capture.json"),
}

require(child["run_id"] == RUN == terminal["run_id"] == manifest["run_id"], "run id")
require(child["source_closure_sha256"] == SOURCE == terminal["source_closure_sha256"] == manifest["source_closure_sha256"], "source closure")
require(child["profile_sha256"] == PROFILE == terminal["profile_sha256"] == manifest["profile_sha256"], "profile")
require(child["completed"] is True and child["source_unchanged"] is True, "child completion/source")
require(len(child["batches"]) == 35 and [x["index"] for x in child["batches"]] == list(range(35)), "35 contiguous child rows")
require(http["run_id"] == RUN and http["eligible_for_dataset"] is False and http["formal_acceptance"] is False, "diagnostic HTTP scope")
obs = http["observation"]
require(obs["unfinished"] == [] and obs["spans_dropped"] == 0 and obs["identity_missing"] == 0, "HTTP recorder completeness")
require(obs["transport_failures_observed"] == 0, "HTTP transport failures")
require(terminal["errors"] == [] and terminal["formal_acceptance"] is False, "terminal cleanup scope")

for role, exit_record in exit_files.items():
    require(exit_record["exit_code"] == 0, f"{role} actual exit")
    capture = captures[role]
    require(capture["actual_process_exit"]["exit_code"] == 0, f"{role} capture exit")
    job = capture["job"]
    require(job["active_count"] == 0 and job["closed"] and job["zero_observed"], f"{role} job cleanup")
    require(not job["handle_retained"] and not job["close_uncertain"], f"{role} handles")

rows = []
for item in child["batches"]:
    index = item["index"]
    joint = read(f"joint-{index:02d}.json")
    native = read(f"project/benchmark/out/batch-{index:02d}.json")
    require(joint["run_id"] == RUN and joint["index"] == index, f"joint {index}")
    require(native["run_id"] == RUN and native["index"] == index, f"native {index}")
    require(joint["native_batch_sha256"] == item["native"]["sha256"], f"native binding {index}")
    require(joint["barrier_receipt"]["objects"]["value"] == 71128, f"objects {index}")
    require(joint["barrier_receipt"]["resources"]["value"] == 6, f"resources {index}")
    rows.append({
        "index": index,
        "objects": joint["barrier_receipt"]["objects"]["value"],
        "resources": joint["barrier_receipt"]["resources"]["value"],
        "max_status_gap_ms": joint["barrier_receipt"]["max_status_gap_ms"],
    })

result = {
    "schema_id": "hh-studio.gt06.s97-terminal-exit-reconciliation",
    "schema_version": "1.0.0",
    "run_id": RUN,
    "source_closure_sha256": SOURCE,
    "profile_sha256": PROFILE,
    "raw_root": str(ROOT).replace("\\", "/"),
    "raw_immutable": True,
    "diagnostic_only": True,
    "formal_acceptance": False,
    "eligible_for_dataset": False,
    "derived_from": {
        "child_result_sha256": sha("child-result.json"),
        "child_terminal_cleanup_sha256": sha("child-terminal-cleanup.json"),
        "diagnostic_manifest_sha256": sha("diagnostic-manifest.json"),
        "http_phases_final_sha256": sha("http-phases-final.json"),
        "host_exit_sha256": sha("host-owner/process-exit.json"),
        "editor_exit_sha256": sha("editor-host/process-exit.json"),
        "import_exit_sha256": sha("import-host/process-exit.json"),
    },
    "actual_exits": {role: record["exit_code"] for role, record in exit_files.items()},
    "cleanup": {
        "all_jobs_zero_closed": True,
        "all_retained_handles_released": True,
        "terminal_errors": [],
        "source_unchanged": True,
    },
    "completed_batches": 35,
    "rows": rows,
    "max_status_gap_ms": max(row["max_status_gap_ms"] for row in rows),
    "objects": sorted({row["objects"] for row in rows}),
    "resources": sorted({row["resources"] for row in rows}),
    "correction": "Raw child/supervisor null exit fields are retained. Outer actual-exit receipts prove host/editor/import exit 0; this derived correction does not infer natural self-exit and does not create acceptance evidence.",
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: result[k] for k in ("schema_id", "run_id", "diagnostic_only", "formal_acceptance", "eligible_for_dataset", "actual_exits", "completed_batches", "max_status_gap_ms", "objects", "resources")}, ensure_ascii=False))
