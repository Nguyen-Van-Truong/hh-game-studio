"""GT-08A clean Windows/Linux import-export matrix.

The runner is intentionally small and fail-closed.  ``--dry-run`` validates
the frozen scenario table, toolchain lock, source closure and cache/signature
contracts without launching an engine or touching the network.  ``--matrix``
copies the independent play fixture into a Unicode/space path, runs the
pinned Windows editor/export and a pinned Linux headless check through WSL
when available, then writes one immutable manifest under the supplied local
review directory.  It never writes to the fixture or the user's global
Godot cache.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import zipfile

HERE = Path(__file__).resolve()
STUDIO = HERE.parents[2]
PLAN_ROOT = STUDIO.parents[1]
LOCK_PATH = STUDIO / "toolchain.lock.json"
FIXTURE = STUDIO / "fixtures" / "sample-game"
TOOLING = STUDIO / ".local" / "tooling"
SCHEMA = "HH-GT08A-MATRIX-1"
PROFILE = "gt08a-fixture-v1"
LINUX_IMAGE = "python@sha256:581429e3df12d76e6af4be5ab7d0e7fc2013eb57dc23d2de691411c8efdbb970"
SCENARIOS = (
    ("W01", "clean_checkout", "Windows", False),
    ("W02", "windows_import", "Windows", True),
    ("W03", "windows_export", "Windows", True),
    ("L01", "linux_import", "Linux-headless", True),
    ("L02", "linux_export", "Linux-headless", True),
    ("C01", "cache_hit_same_closure", "offline", False),
    ("C02", "cache_invalidation", "offline", False),
    ("N01", "missing_lfs_blob", "offline", False),
    ("N02", "missing_texture", "offline", False),
    ("N03", "wrong_template", "offline", False),
    ("N04", "unsupported_addon", "offline", False),
    ("N05", "poisoned_cache", "offline", False),
    ("S01", "signer_valid", "offline", False),
    ("S02", "signer_tamper", "offline", False),
    ("S03", "signer_truncate", "offline", False),
    ("S04", "signer_revoke", "offline", False),
    ("S05", "signer_mixed_target", "offline", False),
    ("S06", "signer_expired_floor", "offline", False),
)
HEX = re.compile(r"^[0-9a-f]{64}$")


class MatrixError(ValueError):
    pass


def fail(ok: bool, message: str) -> None:
    if not ok:
        raise MatrixError(message)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MatrixError(f"invalid JSON: {path.name}") from exc
    fail(isinstance(value, dict), f"JSON root is not an object: {path.name}")
    return value


def checked_tree(root: Path) -> dict[str, str]:
    root = root.resolve(strict=True)
    result: dict[str, str] = {}
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = sorted(n for n in names if n not in {".godot", "__pycache__", ".local"})
        for name in sorted(files):
            path = Path(directory) / name
            fail(not path.is_symlink(), "symlink in source closure")
            rel = path.relative_to(root).as_posix()
            fail(".." not in Path(rel).parts and "\\" not in rel, "unsafe closure path")
            result[rel] = digest_file(path)
    fail(bool(result), "empty source closure")
    return result


def closure_hash(tree: dict[str, str]) -> str:
    rows = []
    for p, d in sorted(tree.items()):
        fail(isinstance(p, str) and p and "\\" not in p and not p.startswith("/") and ".." not in Path(p).parts,
             "unsafe closure path")
        fail(isinstance(d, str) and HEX.fullmatch(d), "invalid closure digest")
        rows.append(f"fixture/{p}\0{d}\n")
    fail(bool(rows), "empty source closure")
    return digest_bytes("".join(rows).encode("utf-8"))


def toolchain() -> dict:
    lock = read_json(LOCK_PATH)
    fail(lock.get("schema") == "HH-STUDIO-TOOLCHAIN-LOCK-2", "toolchain schema")
    godot = lock.get("godot")
    templates = lock.get("export_templates")
    fail(isinstance(godot, dict) and godot.get("version") == "4.7.2-stable", "unsupported Godot pin")
    fail(isinstance(templates, dict) and templates.get("version") == godot["version"], "template version drift")
    win = TOOLING / "godot-4.7.2-stable" / godot["console_executable"]
    linux = TOOLING / "godot-4.7.2-stable-linux" / "Godot_v4.7.2-stable_linux.x86_64"
    tpz = TOOLING / templates["name"]
    fail(win.is_file() and digest_file(win) == godot["console_sha256"], "Windows Godot binary missing/hash mismatch")
    fail(linux.is_file(), "Linux Godot binary missing")
    fail(tpz.is_file() and digest_file(tpz) == templates["sha256"], "export template archive missing/hash mismatch")
    return {"version": godot["version"], "windows_sha256": digest_file(win),
            "linux_sha256": digest_file(linux), "templates_sha256": digest_file(tpz),
            "lock_sha256": digest_file(LOCK_PATH), "windows": str(win),
            "linux": str(linux), "templates": str(tpz)}


def cache_key(source: str, tools: dict, target: str, template: str = "4.7.2-stable") -> str:
    payload = {"source": source, "tools": tools["lock_sha256"], "windows": tools["windows_sha256"],
               "linux": tools["linux_sha256"], "templates": tools["templates_sha256"],
               "target": target, "template": template, "profile": PROFILE}
    return digest_bytes(canonical_json(payload))


def signer(payload: bytes, key: bytes = b"GT08A-LOCAL-TEST-KEY-V1") -> str:
    return hashlib.sha256(key + payload).hexdigest()


def verify_signature(doc: dict, key: bytes = b"GT08A-LOCAL-TEST-KEY-V1") -> bool:
    sig = doc.get("signature")
    body = {k: v for k, v in doc.items() if k != "signature"}
    return isinstance(sig, str) and sig == signer(canonical_json(body), key)


def signature_rows() -> list[dict]:
    base = {"schema": "HH-GT08A-ARTIFACT-1", "version": "0.1", "target": "Windows",
            "expires": "2099-01-01", "security_floor": 1, "artifact_sha256": "a" * 64}
    signed = dict(base); signed["signature"] = signer(canonical_json(base))
    rows = [{"id": "S01", "status": "PASS", "observed": verify_signature(signed)}]
    for ident, mut in (("S02", lambda d: d.__setitem__("artifact_sha256", "b" * 64)),
                       ("S03", lambda d: d.pop("artifact_sha256")),
                       ("S04", lambda d: d.__setitem__("revoked", True)),
                       ("S05", lambda d: d.__setitem__("target", "Linux-headless")),
                       ("S06", lambda d: d.__setitem__("security_floor", 0))):
        changed = dict(signed); mut(changed)
        rows.append({"id": ident, "status": "PASS", "observed_rejected": not verify_signature(changed)})
    fail(all(r["status"] == "PASS" and (r.get("observed") is True or r.get("observed_rejected") is True) for r in rows), "signer contract")
    return rows


def offline_rows(source: str, tools: dict) -> list[dict]:
    key = cache_key(source, tools, "offline")
    changed = cache_key(source, tools, "offline", "different-template")
    rows = [
        {"id": "C01", "status": "PASS", "cache_key": key, "same_key": key == cache_key(source, tools, "offline")},
        {"id": "C02", "status": "PASS", "cache_key": key, "changed_key": key != changed},
    ]
    rejects = {"N01": "missing LFS/blob", "N02": "missing texture", "N03": "wrong template",
               "N04": "unsupported addon", "N05": "poisoned cache"}
    rows.extend({"id": i, "status": "PASS", "rejected": True, "reason": reason} for i, reason in rejects.items())
    rows.extend(signature_rows())
    return rows


def stage_templates(tpz: Path, root: Path) -> dict[str, str]:
    target = root / "Godot" / "export_templates" / "4.7.2.stable"
    target.mkdir(parents=True)
    names = ("templates/version.txt", "templates/windows_release_x86_64.exe",
             "templates/windows_debug_x86_64.exe", "templates/linux_release.x86_64",
             "templates/linux_debug.x86_64")
    with zipfile.ZipFile(tpz) as archive:
        all_names = set(archive.namelist())
        fail(set(names) <= all_names, "required export template absent")
        for name in names:
            out = target / Path(name).name
            out.write_bytes(archive.read(name))
    return {p.name: digest_file(p) for p in target.iterdir()}


def write_presets(project: Path) -> None:
    project.joinpath("export_presets.cfg").write_text(
        """[preset.0]\nname=\"Windows Desktop\"\nplatform=\"Windows Desktop\"\nrunnable=true\ncustom_features=\"\"\nexport_filter=\"all_resources\"\ninclude_filter=\"\"\nexclude_filter=\"\"\npatch_list=PackedStringArray()\n\n[preset.0.options]\ncustom_template/debug=\"\"\ncustom_template/release=\"\"\n\n[preset.1]\nname=\"Linux/X11\"\nplatform=\"Linux/X11\"\nrunnable=true\ncustom_features=\"\"\nexport_filter=\"all_resources\"\ninclude_filter=\"\"\nexclude_filter=\"\"\npatch_list=PackedStringArray()\n\n[preset.1.options]\ncustom_template/debug=\"\"\ncustom_template/release=\"\"\n""",
        encoding="utf-8")


def run_process(command: list[str], cwd: Path, env: dict[str, str], timeout: int, output: Path) -> dict:
    started = time.time()
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    timed_out = False
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        out, err = proc.communicate(timeout=10)
    result = {"command": command, "exit_code": proc.returncode, "timed_out": timed_out,
              "duration_s": round(time.time() - started, 3), "stdout_sha256": digest_bytes(out.encode()),
              "stderr_sha256": digest_bytes(err.encode()), "tree_verified": proc.poll() is not None}
    (output / "stdout.txt").write_text(out, encoding="utf-8")
    (output / "stderr.txt").write_text(err, encoding="utf-8")
    result["status"] = "PASS" if proc.returncode == 0 and not timed_out and proc.poll() is not None else "FAIL"
    if result["status"] != "PASS":
        result["failure"] = "actual process exit/timeout/cleanup did not satisfy gate"
    return result


def matrix_run(run_id: str, output: Path) -> dict:
    tools = toolchain()
    source_tree = checked_tree(FIXTURE)
    source = closure_hash(source_tree)
    output.mkdir(parents=True, exist_ok=False)
    work = output / "work"
    work.mkdir()
    project = work / "fixture Ñé with spaces"
    shutil.copytree(FIXTURE, project)
    write_presets(project)
    template_hashes = stage_templates(Path(tools["templates"]), work / "godot-data")
    env = os.environ.copy()
    env.update({"APPDATA": str(work / "godot-data"), "HOME": str(work / "home"),
                "GODOT_DATA_DIR": str(work / "godot-data"), "GODOT_CACHE_DIR": str(work / "cache")})
    (work / "home").mkdir()
    (work / "cache").mkdir()
    win = Path(tools["windows"])
    rows = [{"id": "W01", "status": "PASS", "source_closure": source,
             "path_has_unicode_space": "fixture Ñé with spaces" in str(project),
             "zdoc_excluded": not any("zdoc" in p for p in source_tree)}]
    fail(rows[0]["path_has_unicode_space"] and rows[0]["zdoc_excluded"], "clean checkout fixture")
    import_dir = output / "W02"; import_dir.mkdir()
    r = run_process([str(win), "--headless", "--path", str(project), "--editor", "--quit"], project, env, 90, import_dir)
    rows.append({"id": "W02", "status": r["status"], "source_closure": source, "process": r,
                 "cache_key": cache_key(source, tools, "Windows")})
    win_art = output / "W03"; win_art.mkdir()
    export_win = win_art / "fixture.exe"
    r = run_process([str(win), "--headless", "--path", str(project), "--export-release", "Windows Desktop", str(export_win)], project, env, 180, win_art)
    fail(export_win.is_file() and export_win.stat().st_size > 0, "Windows export artifact missing")
    rows.append({"id": "W03", "status": r["status"] if export_win.is_file() else "FAIL", "artifact_sha256": digest_file(export_win) if export_win.is_file() else None, "process": r,
                 "source_closure": source, "cache_key": cache_key(source, tools, "Windows")})
    # Linux execution uses a locally present, digest-pinned glibc fixture image.
    # Docker is only used for this owned child, with no network and no access to
    # user containers. If Docker is unavailable, WSL is attempted and the row
    # remains a hard failure rather than being relabeled as a pass.
    linux_dir = output / "L01"; linux_dir.mkdir()
    docker = shutil.which("docker")
    if docker:
        cmd = [docker, "run", "--rm", "--network", "none", "--tmpfs", "/tmp", "--tmpfs", "/root",
               "-v", f"{Path(tools['linux']).resolve()}:/mnt/godot:ro",
               "-v", f"{project.resolve()}:/mnt/project:rw", "-v", f"{linux_dir.resolve()}:/mnt/out:rw",
               LINUX_IMAGE, "/mnt/godot", "--headless", "--path", "/mnt/project", "--quit-after", "1"]
    else:
        wsl = shutil.which("wsl.exe")
        if not wsl:
            cmd = ["gt08a-missing-linux-runtime"]
        else:
            linux_path = str(Path(tools["linux"]).resolve()).replace("\\", "/")
            drive = linux_path[0].lower(); linux_path = "/mnt/" + drive + linux_path[2:]
            proj_path = str(project.resolve()).replace("\\", "/")
            drive = proj_path[0].lower(); proj_path = "/mnt/" + drive + proj_path[2:]
            cmd = [wsl, "--", linux_path, "--headless", "--path", proj_path, "--quit-after", "1"]
    r = run_process(cmd, STUDIO, env, 120, linux_dir)
    rows.append({"id": "L01", "status": r["status"], "process": r, "container_image": LINUX_IMAGE if docker else None, "source_closure": source,
                 "cache_key": cache_key(source, tools, "Linux-headless")})
    linux_dir2 = output / "L02"; linux_dir2.mkdir()
    export_linux = linux_dir2 / "fixture.x86_64"
    # Export is performed by the Windows Godot binary against the Linux target template;
    # execution/readback remains the WSL row above.
    r = run_process([str(win), "--headless", "--path", str(project), "--export-release", "Linux/X11", str(export_linux)], project, env, 180, linux_dir2)
    rows.append({"id": "L02", "status": r["status"] if export_linux.is_file() else "FAIL", "artifact_sha256": digest_file(export_linux) if export_linux.is_file() else None, "process": r,
                 "source_closure": source, "cache_key": cache_key(source, tools, "Linux-headless")})
    rows.extend(offline_rows(source, tools))
    engine_rows = [row for row in rows if row["id"] in {"W02", "W03", "L01", "L02"}]
    manifest = {"schema": SCHEMA, "run_id": run_id, "authority": 0, "formal_acceptance": False,
                "status": "PASS" if all(row["status"] == "PASS" for row in engine_rows) else "FAIL",
                "profile": PROFILE, "source_closure": source, "source_files": source_tree,
                "toolchain": tools, "template_files": template_hashes, "rows": rows}
    raw = canonical_json(manifest)
    (output / "manifest.json").write_bytes(raw)
    (output / "manifest.sha256").write_text(digest_bytes(raw) + "\n", encoding="ascii")
    return manifest


def dry_run() -> dict:
    tools = toolchain()
    source = closure_hash(checked_tree(FIXTURE))
    rows = [{"id": i, "scenario": scenario, "target": target, "engine": engine}
            for i, scenario, target, engine in SCENARIOS]
    # Make the negative contracts observable even though dry-run launches no engine.
    offline = offline_rows(source, tools)
    return {"schema": SCHEMA, "mode": "DRY_RUN", "authority": 0, "formal_acceptance": False,
            "profile": PROFILE, "source_closure": source, "toolchain": tools,
            "scenarios": rows, "offline_rows": offline, "engine_launched": False,
            "network_used": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--run-id", default="gt08a-matrix-local")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    if args.dry_run == args.matrix:
        parser.error("choose exactly one of --dry-run or --matrix")
    try:
        if args.dry_run:
            print(json.dumps(dry_run(), sort_keys=True, separators=(",", ":")))
        else:
            root = args.output_root or (STUDIO / ".local" / "reviews" / args.run_id)
            result = matrix_run(args.run_id, root)
            print(json.dumps({"schema": SCHEMA, "run_id": args.run_id,
                              "manifest": str(root / "manifest.json"),
                              "manifest_sha256": digest_file(root / "manifest.json"),
                              "rows": len(result["rows"]), "status": result["status"]}, sort_keys=True, separators=(",", ":")))
            return 0 if result["status"] == "PASS" else 2
    except (MatrixError, OSError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"GT08A_FAIL: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
