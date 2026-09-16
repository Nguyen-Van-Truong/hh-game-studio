"""Read-only consistency audit of the exact GT04 Blender -02 capture."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

HH3D = Path(__file__).resolve().parents[3]
PACKAGE = HH3D / "zdoc/reviews/20260917-gt04-blender-02"
STUDIO = HH3D / "studio"
CLOSURE = "6190abcf73ab5c01e2e5799ed5210179b771a4165f76a430a3275948c729b847"
BINARY = "8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06"
SOURCES = {
    "blender-addon/README.md": "bcf2ea1af7afc951f6f4995e11ebc398b325801c5a23935d8ae4cb11364f520c",
    "blender-addon/adapter.py": "e6fdbd9d292b8b7aa0a9ba455a89e8336d8e2b354c82adaac3dfe39fc5080358",
    "blender-addon/contract.py": "034b86182742e444a74b645761f34641b4cd576b0fb4a43e43e4e6c0a7e54e25",
    "build/bootstrap/run_fixture.py": "ea522450acc46f90be5e2a7b9257e73ce8b619948105b2c9073aac1f881c7328",
    "tests/blender/blender_probe.py": "74eac1188b8507201a046dab6b8eb5ebb9d5a4d6033493ec1aa45cdc18451778",
    "tests/blender/run_blender_probe.py": "9f11be8a3ad3c2dee621e5449de001d537083d859d7f276fef04347aab0b1cfa",
    "tests/blender/test_contract.py": "4929d9e5128eb176f47ff1740d25f33d0f76a3e11898074a7bcbaf8f3ebfe531",
    "tests/blender/test_probe_evidence.py": "545ded79f7f3e840b65ce412625f0ef1a4bbba8bc9b9bc8c88b9b45bd92b5574",
    "toolchain.lock.json": "28bdce555e9a44ef68193723d512feda02c42a417ceb78faf0b29f52d095dca9",
}
SAVED = {"name": "fixture.blend", "size_bytes": 86917, "sha256": "66db2eb2b068ab04ee3ba5549b8a1f60d869e36975f8733bcf4ed394267b0fe5"}
CHECKPOINT = {"name": "checkpoint.blend", "size_bytes": 85671, "sha256": "c6492012f9b793523c06426f208e195cd8e12d8ce19c3c4f23689c7485fbfe4b"}
REVISION = "sha256:658a55c1341ce7ee82c358e7fe019964c8c46c884a9f773a02daa171b2026a30"
EMPTY_REVISION = "sha256:30bf66b61ef6ccda3a2724338925481cb04d89bd990815d8a30ed309e3b789e3"
COUNTS = {"edit": 27, "reopen": 9, "checkpoint": 7}
ARTIFACT_PATHS = ({"source/studio/" + path for path in SOURCES} |
                  {phase + suffix for phase in ("python", "edit", "reopen", "checkpoint")
                   for suffix in ("-host.json", "-stdout.txt", "-stderr.txt")} |
                  {"fixture/" + name for name in ("checkpoint.blend", "fixture.blend", "expected.json", "edit-result.json", "reopen-result.json", "checkpoint-result.json")} |
                  {"blender-user/extensions/.cache/compat.dat"})


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256")
    return digest.hexdigest()


def pairs(rows):
    value = {}
    for key, item in rows:
        need(key not in value, "duplicate JSON field")
        value[key] = item
    return value


def loads(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def read_json(path):
    need(path.stat().st_size <= 1024 * 1024, "oversized JSON evidence")
    return loads(path.read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def unlinked(path):
    for part in (path, *path.parents):
        need(not part.is_symlink() and not (getattr(part.lstat(), "st_file_attributes", 0) & 0x400), "linked evidence path")


def inventory(root):
    result = {}
    unlinked(root)
    for path in root.rglob("*"):
        unlinked(path)
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if "__pycache__" in path.parts:
                need(relative.startswith("source/studio/") and path.suffix == ".pyc", "unexpected excluded cache")
                continue
            if relative != "result.json":
                result[relative] = sha(path)
    return result


def required_labels(snapshot):
    # Reuse the frozen runner's exact label declaration without importing or
    # executing its code. Its source SHA is checked against SOURCES first.
    tree = ast.parse((snapshot / "tests/blender/run_blender_probe.py").read_text(encoding="utf-8"))
    rows = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "REQUIRED" for target in node.targets)]
    need(len(rows) == 1 and {key: len(value) for key, value in rows[0].items()} == COUNTS, "frozen labels/counts differ")
    return rows[0]


def native(phase, report, raw, labels):
    need(type(report) is dict and set(report) == {"schema", "phase", "version", "actual_blender", "ok", "checks", "public_ack", "acceptance", "result"}, "native fields")
    need(report["schema"] == "HH-GT04-NATIVE-PROBE-1" and report["phase"] == phase and report["version"] == "5.2.1 LTS", "native identity")
    need(report["actual_blender"] is True and report["ok"] is True and report["public_ack"] is False and report["acceptance"] is False, "native flags")
    expected = [{"label": label, "passed": True} for label in labels]
    rows = [loads(line[len("GT04_CHECK "):]) for line in raw.splitlines() if line.startswith("GT04_CHECK ")]
    finals = [loads(line[len("GT04_RESULT "):]) for line in raw.splitlines() if line.startswith("GT04_RESULT ")]
    for checks in (report["checks"], rows):
        need(type(checks) is list and len(checks) == COUNTS[phase], "native count")
        need(all(type(row) is dict and set(row) == {"label", "passed"} and row["passed"] is True for row in checks), "native check type/false")
        need(checks == expected, "native labels/order")
    need(len(finals) == 1 and canonical(finals[0]) == canonical(report), "raw final mismatch")
    need(not re.search(r"(?i)\b(warning|error|traceback|fatal)\b", raw), "native diagnostic")


def verify(package=PACKAGE, studio=STUDIO):
    package, studio = Path(package), Path(studio)
    report = read_json(package / "result.json")
    need(report.get("schema") == "HH-GT04-FROZEN-PROBE-1" and report.get("ok") is True, "capture did not pass")
    need(report.get("acceptance") is False and report.get("public_ack") is False and "failure" not in report, "capture authority/failure")
    need(type(report.get("python_tests")) is int and report["python_tests"] == 18 and report.get("native_checks") == COUNTS, "capture counts")
    need(all(type(value) is int for value in report["native_checks"].values()), "typed native counts")
    need(type(report.get("artifacts")) is dict and set(report["artifacts"]) == ARTIFACT_PATHS, "artifact membership mismatch")
    need(report["artifacts"] == inventory(package), "artifact inventory/hash mismatch")
    need(report.get("source_files") == SOURCES and report.get("source_closure_sha256") == CLOSURE, "source manifest mismatch")
    closure = hashlib.sha256("".join(f"8-9-hh3d-3/studio/{path}\0{digest}\n" for path, digest in sorted(SOURCES.items())).encode()).hexdigest()
    need(closure == CLOSURE, "pinned closure mismatch")
    snapshot = package / "source/studio"
    for root in (studio, snapshot):
        actual = {path.relative_to(root).as_posix() for folder in ("blender-addon", "tests/blender")
                  for path in (root / folder).rglob("*") if path.is_file() and "__pycache__" not in path.parts}
        need(actual == set(SOURCES) - {"build/bootstrap/run_fixture.py", "toolchain.lock.json"}, "source membership drift")
        for relative, digest in SOURCES.items():
            path = root / relative
            unlinked(path)
            need(sha(path) == digest, "source bytes drift: " + relative)
    need(all(report.get(key) is True for key in ("source_unchanged", "snapshot_unchanged", "binary_unchanged")), "capture drift flags")
    binary = studio / ".local/tooling/blender-5.2.1-windows-x64/blender.exe"
    unlinked(binary)
    need(report.get("binary_sha256") == BINARY and sha(binary) == BINARY, "binary pin mismatch")
    labels = required_labels(snapshot)
    runs = report.get("runs")
    need(type(runs) is list and len(runs) == 4, "four actual processes required")
    previous = datetime.fromisoformat(report["started_at"])
    end = datetime.fromisoformat(report["completed_at"])
    pids, native_reports = [], {}
    for phase, run in zip(("python", "edit", "reopen", "checkpoint"), runs):
        need(all(run.get(key) == phase + suffix for key, suffix in (("host", "-host.json"), ("stdout", "-stdout.txt"), ("stderr", "-stderr.txt"))), "process evidence paths")
        host = read_json(package / run["host"])
        need(set(host) == {"target_pid", "started_at", "exit_code"}, "host fields")
        for record, fields in ((host, ("target_pid", "exit_code")), (run, ("target_pid", "wrapper_pid", "exit_code", "wrapper_exit_code"))):
            need(all(type(record.get(field)) is int for field in fields), "host integer types")
        need(host["target_pid"] == run["target_pid"] > 0 and run["wrapper_pid"] > 0 and host["exit_code"] == run["exit_code"] == run["wrapper_exit_code"] == 0, "actual process exit/PID")
        need(run.get("timed_out") is False and run.get("tree_verified") is True and run.get("ownership") == "gated_job_kill_on_close", "process ownership/tree")
        wrapper_time, target_time = datetime.fromisoformat(run["started_at"]), datetime.fromisoformat(host["started_at"])
        need(previous <= wrapper_time <= target_time <= end, "process chronology")
        previous = target_time
        pids.extend((run["target_pid"], run["wrapper_pid"]))
        raw = (package / run["stdout"]).read_text(encoding="utf-8")
        stderr = (package / run["stderr"]).read_text(encoding="utf-8")
        if phase == "python":
            need(run["argv"] == ["python.exe", "-B", "-m", "unittest", "discover", "-s", "$SNAPSHOT/tests/blender", "-p", "test_*.py", "-v"], "Python argv")
            need(raw == "" and re.search(r"Ran 18 tests in [\d.]+s\s+OK\s*\Z", stderr) is not None, "raw unittest completion")
            need(len(re.findall(r"^test_.* \.\.\. ok$", stderr, re.M)) == 18 and not re.search(r"(?i)\b(skip|skipped|error|failure|failed)\b", stderr), "raw unittest rows")
        else:
            need(run["argv"] == ["blender.exe", "--background", "--factory-startup", "--disable-autoexec", "--offline-mode", "--threads", "1", "--python-exit-code", "17", "--python", "$SNAPSHOT/tests/blender/blender_probe.py", "--", "--phase", phase, "--owned-root", "fixture"], "Blender argv")
            need(stderr == "", "native stderr")
            value = read_json(package / "fixture" / (phase + "-result.json"))
            native(phase, value, raw, labels[phase])
            native_reports[phase] = value["result"]
    need(len(set(pids)) == 8, "distinct captured process identities")
    expected = read_json(package / "fixture/expected.json")
    need(set(expected) == {"snapshot", "revision", "saved", "checkpoint"} and expected["revision"] == REVISION, "expected scene metadata")
    need(native_reports["edit"] == expected and native_reports["reopen"] == {key: expected[key] for key in ("snapshot", "revision", "saved")}, "save/reopen result mismatch")
    for key, artifact in (("saved", SAVED), ("checkpoint", CHECKPOINT)):
        need(canonical(expected[key]) == canonical(artifact) and canonical(report.get(key)) == canonical(artifact), "fixed artifact descriptor")
        path = package / "fixture" / artifact["name"]
        need(path.stat().st_size == artifact["size_bytes"] and sha(path) == artifact["sha256"], "saved/checkpoint bytes")
    need("sha256:" + hashlib.sha256(canonical(expected["snapshot"])).hexdigest() == REVISION, "native semantic hash")
    empty = {"schema": "HH-BLENDER-FIXTURE-SCENE-1", "objects": [], "units": {"scale_length": 1.0, "system": "METRIC"}}
    need(canonical(native_reports["checkpoint"]) == canonical({"snapshot": empty, "revision": EMPTY_REVISION, "saved": CHECKPOINT}), "checkpoint readback")
    need("sha256:" + hashlib.sha256(canonical(empty)).hexdigest() == EMPTY_REVISION, "checkpoint semantic hash")
    return {"ok": True, "acceptance": False, "public_ack": False, "source_closure_sha256": CLOSURE,
            "python_tests": 18, "native_checks": COUNTS, "artifact_count": len(report["artifacts"]),
            "result_sha256": sha(package / "result.json"), "scope": "historical raw-evidence consistency; no live engine or independent critic claim"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(verify(), sort_keys=True))
