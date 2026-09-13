"""Read-only, fail-closed binder for GT-01 candidate evidence."""
from __future__ import annotations
import argparse, hashlib, json, math, os, re, stat
from datetime import datetime
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"^[0-9a-f]{64}$")
PREFIX = "8-9-hh3d-3/studio/"
SAFE = re.compile(r"^[A-Za-z0-9._/-]+$")
LANES = ("import", "parse", "trace-headless", "editor-headed", "trace-headed")

class BindError(ValueError): pass

def _pairs(items):
    out = {}
    for key, value in items:
        if key in out: raise BindError("duplicate JSON key: " + str(key))
        out[key] = value
    return out

def load_json(path: Path) -> dict[str, Any]:
    try: value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, BindError) as exc: raise BindError("invalid JSON: " + path.name) from exc
    if not isinstance(value, dict): raise BindError("JSON root is not object: " + path.name)
    return value

def _rel(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/") or not SAFE.fullmatch(value):
        raise BindError("unsafe relative path")
    parts = value.split("/")
    if any(p in ("", ".", "..") for p in parts): raise BindError("path traversal")
    return "/".join(parts)

def _source_records(manifest: dict[str, Any]) -> dict[str, str]:
    if manifest.get("schema") != "HH3D-GT01-SOURCE-CLOSURE-2" or manifest.get("status") not in ("CANDIDATE", "FROZEN"):
        raise BindError("invalid source manifest status/schema")
    if manifest.get("gaps") not in (None, []): raise BindError("source manifest contains gaps")
    rows = manifest.get("required_files")
    if not isinstance(rows, list) or not rows: raise BindError("required_files missing or empty")
    result = {}
    for row in rows:
        if not isinstance(row, dict): raise BindError("malformed source record")
        key = row.get("path")
        if not isinstance(key, str) or not key.startswith(PREFIX): raise BindError("source path must use exact studio prefix")
        rel = _rel(key[len(PREFIX):]); digest = row.get("sha256")
        if not isinstance(digest, str) or not HEX64.fullmatch(digest): raise BindError("invalid source digest: " + rel)
        if row.get("required") is not True or row.get("exists") is not True or row.get("regular") is not True or row.get("symlink") or row.get("reparse") or row.get("hard_links") != 1: raise BindError("unsafe source identity: " + rel)
        if rel in result: raise BindError("duplicate source path: " + rel)
        result[rel] = digest
    return result

def closure_sha256(records: dict[str, str]) -> str:
    return hashlib.sha256("".join(f"{PREFIX}{p}\0{records[p]}\n" for p in sorted(records)).encode()).hexdigest()

def _safe_path(root: Path, rel: str) -> Path:
    raw = root / Path(rel); cur = raw
    while True:
        try: info = os.lstat(cur)
        except FileNotFoundError: info = None
        except OSError as exc: raise BindError("source path unavailable") from exc
        if info is not None and (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400): raise BindError("symlink/reparse source path")
        if cur == cur.parent: break
        cur = cur.parent
    resolved_root = root.resolve(strict=True); resolved = raw.resolve(strict=False)
    try: resolved.relative_to(resolved_root)
    except ValueError as exc: raise BindError("source path escapes repo root") from exc
    return resolved

def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def _check_disk(repo: Path, records: dict[str, str]) -> None:
    studio = _safe_path(repo, PREFIX.rstrip("/"))
    actual = {}
    excluded = {".godot", ".local", "__pycache__", "evidence"}
    for directory, names, files in os.walk(studio, followlinks=False):
        d = Path(directory)
        names[:] = sorted(n for n in names if n not in excluded)
        for name in names:
            info = os.lstat(d / name)
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise BindError("unsafe source directory")
        for name in sorted(files):
            p = d / name
            if p.suffix in (".pyc", ".pyo", ".tmp", ".swp"): continue
            try: info = os.lstat(p)
            except OSError as exc: raise BindError("source path unavailable") from exc
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1: raise BindError("unsafe source file")
            actual[p.relative_to(studio).as_posix()] = _sha(p)
    if set(actual) != set(records): raise BindError("source closure file set mismatch")
    for rel, expected in records.items():
        p = _safe_path(repo, PREFIX + rel)
        try: info = os.lstat(p)
        except OSError as exc: raise BindError("missing source: " + rel) from exc
        if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1: raise BindError("unsafe source file: " + rel)
        if _sha(p) != expected: raise BindError("source digest mismatch: " + rel)

def _log_path(evidence: Path, value: Any) -> Path:
    rel = _rel(value); root = evidence.parent.resolve(strict=True); p = _safe_path(root, rel)
    try: p.relative_to(root)
    except ValueError as exc: raise BindError("log path escapes evidence directory") from exc
    return p

def _time(value: Any) -> datetime:
    if not isinstance(value, str): raise BindError("invalid host timestamp")
    try: return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc: raise BindError("invalid host timestamp") from exc

def _parse_trace(line: str) -> dict[str, Any]:
    if not line.startswith("GT01_TRACE "): raise BindError("trace prefix missing")
    try: data = json.loads(line[len("GT01_TRACE "):], object_pairs_hook=_pairs)
    except (json.JSONDecodeError, BindError) as exc: raise BindError("trace JSON invalid") from exc
    if not isinstance(data, dict) or data.get("result") != "PASS" or data.get("phase") != "QUITTING": raise BindError("trace is not passing")
    obs = data.get("observations"); labels = ["menu","start","moved","paused_frozen","resumed","quitting"]
    if not isinstance(obs, list) or len(obs) != len(labels) or [x.get("label") for x in obs if isinstance(x, dict)] != labels: raise BindError("trace observations incomplete/out of order")
    if not all(isinstance(x, dict) and isinstance(x.get("phase"), str) and isinstance(x.get("sim_tick"), int) and not isinstance(x.get("sim_tick"), bool) for x in obs): raise BindError("trace observation types invalid")
    if [x["phase"] for x in obs] != ["MENU","PLAY","PLAY","PAUSED","PLAY","QUITTING"]: raise BindError("trace phases invalid")
    if not isinstance(data.get("sim_tick"), int) or data["sim_tick"] != obs[-1]["sim_tick"]: raise BindError("trace final tick invalid")
    for x in obs:
        b,f=x.get("body"),x.get("focus")
        if not isinstance(b,list) or len(b)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in b) or not isinstance(f,str) or not f: raise BindError("trace state invalid")
    ticks=[x["sim_tick"] for x in obs]
    if any(b<a for a,b in zip(ticks,ticks[1:])) or obs[2]["body"][0]<=obs[1]["body"][0] or ticks[3]!=ticks[2]+1 or obs[3]["body"]!=obs[4]["body"] or ticks[4]<=ticks[3]: raise BindError("trace postconditions invalid")
    return data

def _parse_editor_trace(line: str) -> dict[str, Any]:
    if not isinstance(line, str) or not line.startswith("GT01_EDITOR_TRACE "):
        raise BindError("editor trace prefix missing")
    try:
        value = json.loads(line[len("GT01_EDITOR_TRACE "):], object_pairs_hook=_pairs)
    except (json.JSONDecodeError, BindError) as exc:
        raise BindError("editor trace JSON invalid") from exc
    if (not isinstance(value, dict) or value.get("result") != "PASS"
            or value.get("scene") != "res://main.tscn" or value.get("visible") is not True):
        raise BindError("editor headed postcondition invalid")
    return value

def _artifact_records(evidence: dict[str, Any], evidence_path: Path,
                      capture_path: str) -> None:
    """Check the captured PNG from bytes and an independently bound digest."""
    raw = evidence.get("artifact_hashes")
    records: dict[str, tuple[str, int | None]] = {}
    if isinstance(raw, dict):
        for name, digest in raw.items():
            if not isinstance(name, str) or not isinstance(digest, str):
                raise BindError("malformed artifact hash")
            records[_rel(name)] = (digest, None)
    elif isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str):
                raise BindError("malformed artifact hash")
            name = _rel(row["path"]); size = row.get("bytes")
            if size is not None and (isinstance(size, bool) or not isinstance(size, int) or size < 0):
                raise BindError("invalid artifact size")
            if name in records: raise BindError("duplicate artifact path")
            records[name] = (row["sha256"], size)
    else:
        raise BindError("artifact_hashes missing")
    if set(records) != {capture_path}:
        raise BindError("artifact hashes do not exactly bind capture")
    digest, size = records[capture_path]
    if not HEX64.fullmatch(digest): raise BindError("invalid artifact digest")
    path = _log_path(evidence_path, capture_path)
    try: blob = path.read_bytes()
    except (OSError, UnicodeError) as exc: raise BindError("capture artifact unavailable") from exc
    if hashlib.sha256(blob).hexdigest() != digest or (size is not None and len(blob) != size):
        raise BindError("stale capture artifact")
    if len(blob) < 24 or blob[:8] != b"\x89PNG\r\n\x1a\n" or int.from_bytes(blob[16:20], "big") != 640 or int.from_bytes(blob[20:24], "big") != 360:
        raise BindError("capture is not a 640x360 PNG")

def _check_runs(evidence_path: Path, evidence: dict[str, Any]) -> None:
    runs, hashes = evidence.get("runs"), evidence.get("log_hashes")
    if not isinstance(runs,list) or not isinstance(hashes,dict): raise BindError("runs/log_hashes missing")
    seen=set(); lane_rows={}; expected_logs=set()
    for run in runs:
        if not isinstance(run,dict): raise BindError("malformed run")
        lane=run.get("lane"); argv=run.get("argv",[])
        if not isinstance(lane,str): raise BindError("run lane missing")
        if lane not in LANES or lane in seen: raise BindError("invalid/duplicate run lane")
        seen.add(lane); lane_rows[lane]=run
        if any(not isinstance(run.get(k),int) or isinstance(run.get(k),bool) or run[k]<=0 for k in ("wrapper_pid","target_pid")) or not isinstance(argv,list) or not argv or not all(isinstance(a,str) and a for a in argv): raise BindError("run identity invalid")
        if lane == "import" and "--import" not in argv: raise BindError("import lane argv mismatch")
        if lane == "parse" and "--check-only" not in argv: raise BindError("parse lane argv mismatch")
        if lane in ("trace-headless", "trace-headed") and "--script" not in argv: raise BindError("trace lane argv mismatch")
        if lane == "editor-headed" and not ("--editor" in argv and "res://main.tscn" in argv): raise BindError("editor lane argv mismatch")
        if run.get("exit_code")!=0 or run.get("wrapper_exit_code")!=0 or run.get("timed_out") is not False or run.get("tree_verified") is not True or run.get("ownership") not in ("gated_job_kill_on_close","process_group"): raise BindError("run did not exit cleanly")
        host_name=run.get("host")
        if not isinstance(host_name, str): raise BindError("host record path missing")
        start=_time(run.get("started_at")); hp=_log_path(evidence_path,host_name); hn=_rel(host_name); expected=hashes.get(hn)
        expected_logs.add(_rel(host_name))
        if not isinstance(expected,str) or not HEX64.fullmatch(expected) or _sha(hp)!=expected: raise BindError("stale/unbound host log")
        host=load_json(hp)
        if (host.get("target_pid")!=run["target_pid"] or host.get("exit_code")!=run["exit_code"]
                or ("wrapper_pid" in host and host.get("wrapper_pid") != run["wrapper_pid"])
                or _time(host.get("started_at"))<start): raise BindError("host record disagrees with run")
        for stream in ("stdout","stderr"):
            name=_rel(run.get(stream)); p=_log_path(evidence_path,name); expected=hashes.get(name)
            expected_logs.add(name)
            if not isinstance(expected,str) or not HEX64.fullmatch(expected) or _sha(p)!=expected: raise BindError("stale/unbound stream log")
            try: text=p.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc: raise BindError("stream is not valid UTF-8") from exc
            if stream=="stderr" and text.strip(): raise BindError("stderr is not empty")
            if re.search(r"(?im)^\s*(?:warning|warn|error|failed|fatal)\b",text): raise BindError("warning/error in log")
            traces=[x for x in text.splitlines() if x.startswith("GT01_TRACE ")] if stream=="stdout" else []
            if lane in ("trace-headless","trace-headed") and stream=="stdout":
                if len(traces)!=1: raise BindError("trace lane must contain exactly one trace")
                td=_parse_trace(traces[0])
                # ``trace_lines`` is the canonical headless trace. A headed
                # run adds capture metadata, so compare it only when the
                # runner publishes its separate headed_trace_lines field.
                reported = evidence.get("trace_lines") if lane == "trace-headless" else evidence.get("headed_trace_lines")
                if lane == "trace-headless" and (not isinstance(reported, list) or reported != traces):
                    raise BindError("reported trace differs from stdout")
                if lane == "trace-headed" and reported is not None and reported != traces:
                    raise BindError("reported headed trace differs from stdout")
                if lane=="trace-headed":
                    cap=td.get("capture")
                    if (not isinstance(cap,dict) or cap.get("size")!=[640,360]
                            or not isinstance(cap.get("display_server"),str)
                            or not cap.get("display_server").strip()
                            or cap.get("display_server").strip().lower()=="headless"):
                        raise BindError("headed capture metadata invalid")
                    capture = run.get("capture_path") or evidence.get("capture_path")
                    if not isinstance(capture, str): raise BindError("headed capture path missing")
                    _artifact_records(evidence, evidence_path, _rel(capture))
            elif traces: raise BindError("unexpected trace in non-trace lane")
    executables = {row["argv"][0] for row in lane_rows.values()}
    # Headless proof uses the pinned console binary while real editor/window
    # proof necessarily uses its GUI companion.  Admit exactly that pair, and
    # reject arbitrary mixed binaries or path-bearing substitutions.
    if len(executables) > 2 or any("/" in value or "\\" in value for value in executables):
        raise BindError("runtime lanes use unexpected executables")
    if len(executables) == 2:
        console = {value for value in executables if value.lower().endswith("_console.exe")}
        companion = executables - console
        if len(console) != 1 or len(companion) != 1 or next(iter(companion)).lower() != next(iter(console)).lower().replace("_console.exe", ".exe"):
            raise BindError("runtime lanes are not pinned console/gui pair")
    if set(hashes) != expected_logs: raise BindError("log_hashes contains missing or unrelated files")
    required={"import","parse","trace-headless"}
    if not required.issubset(seen) or seen-required not in (set(),{"editor-headed","trace-headed"}): raise BindError("required/optional lane set invalid")
    if "editor-headed" in seen or "trace-headed" in seen:
        if not {"editor-headed","trace-headed"}.issubset(seen): raise BindError("headed lanes must be paired")
        ed=lane_rows["editor-headed"]
        try: editor_text = _log_path(evidence_path,_rel(ed["stdout"])).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc: raise BindError("editor stream is not valid UTF-8") from exc
        lines=[x for x in editor_text.splitlines() if x.startswith("GT01_EDITOR_TRACE ")]
        if len(lines)!=1: raise BindError("editor headed trace missing")
        payload = _parse_editor_trace(lines[0])
        reported = evidence.get("editor_trace_lines")
        if not isinstance(reported, list) or reported != lines: raise BindError("reported editor trace differs from stdout")
    else:
        if evidence.get("artifact_hashes") not in (None, {}, []): raise BindError("unexpected artifacts without headed capture")

def bind(source_manifest: Path, runner_output: Path, repo_root: Path) -> dict[str, Any]:
    failures=[]; source_hash=None; run_id=command_id=None
    try:
        manifest,evidence=load_json(source_manifest),load_json(runner_output)
        if evidence.get("schema") != "hh-gt01-bootstrap-evidence-v2": raise BindError("unsupported runner evidence schema")
        run_id,command_id=evidence.get("run_id"),evidence.get("command_id")
        if not isinstance(run_id,str) or not run_id or not isinstance(command_id,str) or not command_id: raise BindError("run/command identity missing")
        records=_source_records(manifest); _check_disk(repo_root,records); source_hash=closure_sha256(records)
        if evidence.get("status")!="CANDIDATE": raise BindError("runner output must remain CANDIDATE")
        bound=evidence.get("source_manifest"); expected_bound=dict(records)
        if not isinstance(bound,dict) or bound!=expected_bound: raise BindError("runner source closure is not exact")
        if evidence.get("source_closure_sha256")!=source_hash: raise BindError("supplied closure hash mismatch")
        checks=evidence.get("checks")
        if not isinstance(checks,dict) or not checks or not all(v is True for v in checks.values()): raise BindError("runtime checks incomplete/failed")
        _check_runs(runner_output,evidence)
    except (BindError, OSError, UnicodeError, ValueError, TypeError) as exc: failures.append(str(exc) or exc.__class__.__name__)
    return {"schema":"HH3D-GT01-EVIDENCE-BINDER-2","status":"READY_FOR_CRITIC" if not failures else "GAP","run_id":run_id,"command_id":command_id,"source_closure_sha256":source_hash if not failures else None,"failures":failures,"limits":["READY_FOR_CRITIC validates candidate facts only; it never upgrades runner status or accepts GT-01", "Packages without editor-headed/trace-headed lanes are explicitly partial headed scope"]}

def main(argv=None) -> int:
    p=argparse.ArgumentParser(); p.add_argument("--source-manifest",required=True,type=Path); p.add_argument("--runner-output",required=True,type=Path); p.add_argument("--repo-root",required=True,type=Path); p.add_argument("--output",required=True,type=Path); a=p.parse_args(argv); result=bind(a.source_manifest,a.runner_output,a.repo_root); a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,indent=2)); return 0 if result["status"]=="READY_FOR_CRITIC" else 2
if __name__=="__main__": raise SystemExit(main())
