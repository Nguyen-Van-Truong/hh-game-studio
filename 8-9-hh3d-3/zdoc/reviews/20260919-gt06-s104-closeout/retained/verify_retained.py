"""Preserve and verify completed S103 diagnostic roots without launching."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import stat


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[4]
HH3D = WORKSPACE / "8-9-hh3d-3"
RAW_BASE = HH3D / "studio/.local/reviews"
S103_OWNED = HH3D / "zdoc/reviews/20260919-gt06-s103-status-gap/owned"
RUNS = (
    "gt06-s103-prefix-preflight-01",
    "gt06-s103-prefix-preflight-02",
    "gt06-s103-prefix-preflight-03",
    "gt06-s103-prefix-preflight-04",
    "gt06-s103-prefix-preflight-05",
    "gt06-s103-prefix-preflight-06",
    "gt06-s103-prefix-01",
)
OVERLAY_SHA256 = "bb137f32f1fae3730cc139f03fc6902813b3742d5a08d437e957e291cfe0ec46"
SOURCE_CLOSURE_SHA256 = "7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467"
PROFILE_SHA256 = "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85"
CURRENT_PARENT_COMMIT = "349dc40aa440c657c6b3ca7ac7e982dcac8dc537"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def regular(path: Path) -> bytes:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.is_symlink() or info.st_nlink != 1:
        raise RuntimeError(f"NOT_PRIVATE_REGULAR:{path}")
    raw = path.read_bytes()
    if len(raw) != info.st_size:
        raise RuntimeError(f"CHANGED_DURING_READ:{path}")
    return raw


def classify(relative: Path) -> str | None:
    parts = {part.lower() for part in relative.parts}
    name = relative.name.lower()
    if parts & {".godot", "appdata", "localappdata", "__pycache__", "cache", "caches"}:
        return "LOCAL_GENERATED_CACHE"
    if "commands" in parts or "commandstore" in parts or name.endswith((".jsonl", ".guard")):
        return "LOCAL_JOURNAL_OR_COMMANDSTORE"
    if any(token in name for token in ("secret", "token", "credential", "password")):
        return "SECRET_OR_TOKEN"
    return None


def closure(files: dict[str, str]) -> str:
    return sha("".join(k + "\0" + files[k] + "\n" for k in sorted(files)).encode())


def read_json(path: Path) -> dict:
    return json.loads(regular(path))


def actual_status(raw: Path, run_id: str) -> dict:
    context = read_json(raw / "context.json")
    source_manifest = read_json(raw / "source-files.json")
    if context.get("run_id") != run_id:
        raise RuntimeError(f"RUN_ID_MISMATCH:{run_id}")
    if source_manifest != context.get("source_files"):
        raise RuntimeError(f"SOURCE_MANIFEST_MISMATCH:{run_id}")
    if len(source_manifest) != 53 or closure(source_manifest) != SOURCE_CLOSURE_SHA256:
        raise RuntimeError(f"SOURCE_CLOSURE_MISMATCH:{run_id}")
    if context.get("source_closure_sha256") != SOURCE_CLOSURE_SHA256:
        raise RuntimeError(f"CONTEXT_SOURCE_PIN:{run_id}")
    if context.get("profile_sha256") != PROFILE_SHA256:
        raise RuntimeError(f"CONTEXT_PROFILE_PIN:{run_id}")
    if context.get("generated_overlay_sha256") != OVERLAY_SHA256:
        raise RuntimeError(f"CONTEXT_OVERLAY_PIN:{run_id}")
    child_expected = context.get("child_script_sha256")
    child_source = raw / "diagnostic-child.py"
    if not child_source.is_file() and run_id in {"gt06-s103-prefix-preflight-06", "gt06-s103-prefix-01"}:
        child_source = S103_OWNED / f"{run_id}.py"
    child = None
    if child_expected:
        if not child_source.is_file():
            raise RuntimeError(f"CHILD_SCRIPT_MISSING:{run_id}")
        child = {"source": child_source.relative_to(WORKSPACE).as_posix(),
                 "sha256": sha(regular(child_source)), "expected_sha256": child_expected,
                 "match": sha(child_source.read_bytes()) == child_expected}
        if not child["match"]:
            raise RuntimeError(f"CHILD_SCRIPT_HASH:{run_id}")
    else:
        child = {"source": None, "sha256": None, "expected_sha256": None,
                 "match": None, "gap": "CONTEXT_CHILD_SCRIPT_HASH_MISSING"}
    result = {}
    for name in ("diagnostic-result.json", "child-failure.json", "child-terminal-cleanup.json"):
        path = raw / name
        if path.is_file():
            result[name] = read_json(path)
    return {"context": context, "child": child, "results": result}


def copy_portable(raw: Path, destination: Path) -> tuple[list[dict], list[dict]]:
    inventory, portable = [], []
    for source in sorted(raw.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(raw)
        data = regular(source)
        row = {"source": source.relative_to(WORKSPACE).as_posix(),
               "relative": relative.as_posix(), "sha256": sha(data), "size_bytes": len(data)}
        reason = classify(relative)
        if reason:
            row["excluded_reason"] = reason
        else:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if regular(target) != data:
                raise RuntimeError(f"COPY_READBACK:{source}")
            row["portable_path"] = target.relative_to(WORKSPACE).as_posix()
            portable.append(row)
        inventory.append(row)
    return inventory, portable


def main() -> int:
    if not RAW_BASE.is_dir() or not S103_OWNED.is_dir():
        raise RuntimeError("S103_ROOTS_MISSING")
    reports, paths = [], []
    for run_id in RUNS:
        raw = RAW_BASE / run_id
        if not raw.is_dir():
            raise RuntimeError(f"RAW_RUN_MISSING:{run_id}")
        checked = actual_status(raw, run_id)
        destination = HERE / run_id
        if destination.exists():
            raise RuntimeError(f"DESTINATION_EXISTS:{run_id}")
        destination.mkdir(parents=True)
        inventory, portable = copy_portable(raw, destination / "portable")
        child = checked["child"]
        if child["match"] is True:
            child_source = WORKSPACE / child["source"]
            child_target = destination / "generated-child.py"
            child_bytes = regular(child_source)
            child_target.write_bytes(child_bytes)
            if regular(child_target) != child_bytes:
                raise RuntimeError(f"CHILD_COPY_READBACK:{run_id}")
            child["retained_path"] = child_target.relative_to(WORKSPACE).as_posix()
            portable.append({"source": child["source"], "relative": "generated-child.py",
                             "sha256": sha(child_bytes), "size_bytes": len(child_bytes),
                             "portable_path": child["retained_path"], "generated_child": True})
        (destination / "raw-inventory.json").write_text(
            json.dumps({"run_id": run_id, "source_root": raw.relative_to(WORKSPACE).as_posix(),
                        "files": inventory}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        reports.append({
            "run_id": run_id, "source_root": raw.relative_to(WORKSPACE).as_posix(),
            "source_file_count": len(checked["context"]["source_files"]),
            "source_closure_sha256": checked["context"]["source_closure_sha256"],
            "profile_sha256": checked["context"]["profile_sha256"],
            "generated_overlay_sha256": checked["context"]["generated_overlay_sha256"],
            "child": checked["child"], "raw_file_count": len(inventory),
            "portable_file_count": len(portable),
            "excluded_file_count": len(inventory) - len(portable),
            "diagnostic_result": checked["results"].get("diagnostic-result.json", {}),
            "child_failure": checked["results"].get("child-failure.json", {}),
            "terminal_cleanup": checked["results"].get("child-terminal-cleanup.json", {}),
        })
        paths.extend({"run_id": run_id, "kind": "portable", "path": row["portable_path"],
                      "sha256": row["sha256"], "size_bytes": row["size_bytes"]} for row in portable)
        paths.append({"run_id": run_id, "kind": "raw-inventory", "path":
                      (destination / "raw-inventory.json").relative_to(WORKSPACE).as_posix()})
    report = {"schema_id": "hh-studio.gt06-s104-retained-s103", "schema_version": "1.0.0",
              "authority": 0, "formal_acceptance": False, "eligible_for_dataset": False,
              "current_parent_commit": CURRENT_PARENT_COMMIT,
              "source_closure_sha256": SOURCE_CLOSURE_SHA256, "profile_sha256": PROFILE_SHA256,
              "generated_overlay_sha256": OVERLAY_SHA256, "runs": reports,
              "gaps": ["editor_target_actual_exit_missing_for_preflight_06_and_prefix_01",
                       "editor_target_actual_exit_not_observed_in_preflight_02_to_05",
                       "preflight_01_owner_start_and_exit_missing",
                       "parent_helper_provenance_after_runs_not_claimed",
                       "diagnostic_prefixes_are_not_acceptance_samples"]}
    (HERE / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (HERE / "paths.json").write_text(json.dumps({"schema_id": "hh-studio.gt06-s104-retained-paths",
        "schema_version": "1.0.0", "paths": paths}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"runs": len(reports), "portable_paths": len(paths),
                      "verification": (HERE / "verification.json").relative_to(WORKSPACE).as_posix()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
