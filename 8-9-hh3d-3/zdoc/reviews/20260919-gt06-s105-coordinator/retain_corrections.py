"""One-shot, read-only raw/Git audit; writes new S105 supplements only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
S104 = HERE.parent / "20260919-gt06-s104-closeout"
PLAN = "8-9-hh3d-3/zdoc/8-9-godot-blender-agent-studio-plan.txt"
COMMIT = "1c6cbbf3cb4f07ccb8b5841c1b9686768ce6c96d"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_new(path: Path, data: bytes) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
    assert path.read_bytes() == data
    return {"path": path.relative_to(REPO).as_posix(), "sha256": sha(data), "size_bytes": len(data)}


def json_new(path: Path, data: dict) -> dict:
    return write_new(path, (json.dumps(data, indent=2, sort_keys=True) + "\n").encode())


def main() -> None:
    entries = json.loads((S104 / "retained/paths.json").read_bytes())["paths"]
    paths = [entry["path"] for entry in entries]
    proc = subprocess.run(["git", "cat-file", "--batch"], input=("".join(COMMIT + ":" + path + "\n" for path in paths)).encode(), stdout=subprocess.PIPE, check=True, cwd=REPO)
    stream = proc.stdout
    offset = 0
    rows = []
    for entry in entries:
        end = stream.index(b"\n", offset)
        header = stream[offset:end].decode()
        offset = end + 1
        if header.endswith(" missing"):
            raise RuntimeError("COMMITTED_FILE_MISSING:" + entry["path"])
        oid, kind, length = header.split()
        assert kind == "blob"
        length = int(length)
        blob = stream[offset:offset + length]
        offset += length + 1
        working = (REPO / entry["path"]).read_bytes()
        if "sha256" in entry and sha(working) != entry["sha256"]:
            raise RuntimeError("WORKING_MANIFEST_MISMATCH:" + entry["path"])
        rows.append({"path": entry["path"], "git_blob_oid": oid,
                     "git_sha256": sha(blob), "working_sha256": sha(working),
                     "manifest_sha256": entry.get("sha256"),
                     "equal": blob == working,
                     "crlf_normalization_only": blob == working.replace(b"\r\n", b"\n")})
    assert offset == len(stream)
    plan = subprocess.check_output(["git", "show", COMMIT + ":" + PLAN], cwd=REPO)
    plan_ref = write_new(HERE / "archive/tools-plan-s104-committed.txt", plan)
    archive = json_new(HERE / "archive/authority.json", {"authority": 0, "source_commit": COMMIT, "source_path": PLAN, "artifact": plan_ref, "note": "Historical exact Git bytes. Current on-disk plan supersedes this archive."})
    generated = []
    for run_id in ("gt06-s103-prefix-preflight-06", "gt06-s103-prefix-01"):
        raw = REPO / "8-9-hh3d-3/studio/.local/reviews" / run_id
        context = json.loads((raw / "context.json").read_bytes())
        source = HERE.parent / "20260919-gt06-s103-status-gap/owned" / (run_id + ".py")
        data = source.read_bytes()
        assert sha(data) == context["child_script_sha256"]
        ref = write_new(HERE / "s103-generated-supplement" / (run_id + ".py"), data)
        generated.append({"run_id": run_id, "source": source.relative_to(REPO).as_posix(), "context_sha256": sha((raw / "context.json").read_bytes()), "artifact": ref, "match": True})
    json_new(HERE / "s104-git-byte-audit.json", {"authority": 0, "formal_acceptance": False,
        "source_commit": COMMIT, "files": rows, "file_count": len(rows),
        "mismatch_count": sum(not row["equal"] for row in rows),
        "note": "Read-only audit before re-staging original working bytes with * -text. No raw evidence altered; no history rewritten.",
        "archive": archive, "generated_child_supplement": generated})
    print(json.dumps({"files": len(rows), "mismatches": sum(not row["equal"] for row in rows), "archive_sha256": plan_ref["sha256"], "generated_children": len(generated)}))


if __name__ == "__main__":
    main()
