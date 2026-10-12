"""hh project / hh scene / hh check: edit any text scene of a registered Godot project.

Flow of ``scene apply``: validate ops on the host -> journal dedupe -> project lock -> refuse if an
editor has the project open -> Godot applies ops in memory and saves a sibling temp .tscn ->
host keeps the original uid, verifies nobody else wrote the scene meanwhile, checkpoints, renames
the temp file into place -> a fresh Godot process reads it back -> receipt is journaled. A failed
readback restores the checkpoint, so nothing is acknowledged that is not on disk.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import secrets
from pathlib import Path
from typing import Any

from . import common as C

CATALOG_PATH = C.GAMEKIT_DIR / "catalog.json"
IMPORT_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".svg", ".tga", ".bmp", ".exr", ".hdr", ".ktx", ".dds",
    ".glb", ".gltf", ".fbx", ".obj", ".blend", ".dae",
    ".wav", ".ogg", ".mp3", ".ttf", ".otf", ".woff", ".woff2", ".fnt",
}
MAX_OPS = 500
MAX_STRING = 200_000
MAX_LIST = 20_000
MAX_DEPTH = 10

_STR = (str,)
_NUM = (int, float)
OPS: dict[str, dict[str, dict[str, Any]]] = {
    "node.create": {"req": {"parent": _STR, "name": _STR, "type": _STR},
                    "opt": {"props": (dict,), "index": (int,), "unique": (bool,)}},
    "node.update": {"req": {"path": _STR, "props": (dict,)}, "opt": {}},
    "node.delete": {"req": {"path": _STR}, "opt": {}},
    "node.move": {"req": {"path": _STR, "parent": _STR}, "opt": {"index": (int,)}},
    "node.rename": {"req": {"path": _STR, "name": _STR}, "opt": {}},
    "node.duplicate": {"req": {"path": _STR, "name": _STR}, "opt": {"props": (dict,)}},
    "resource.new": {"req": {"path": _STR, "prop": _STR, "type": _STR}, "opt": {"props": (dict,)}},
    "resource.load": {"req": {"path": _STR, "prop": _STR, "res": _STR}, "opt": {}},
    "resource.update": {"req": {"path": _STR, "prop": _STR, "props": (dict,)}, "opt": {}},
    "script.attach": {"req": {"path": _STR, "script": _STR}, "opt": {"props": (dict,)}},
    "script.detach": {"req": {"path": _STR}, "opt": {}},
    "instance.add": {"req": {"parent": _STR, "scene": _STR}, "opt": {"name": _STR, "props": (dict,)}},
    "signal.connect": {"req": {"from": _STR, "signal": _STR, "to": _STR, "method": _STR},
                       "opt": {"binds": (list,), "flags": (int,)}},
    "signal.disconnect": {"req": {"from": _STR, "signal": _STR, "to": _STR, "method": _STR}, "opt": {}},
    "group.add": {"req": {"path": _STR, "group": _STR}, "opt": {}},
    "group.remove": {"req": {"path": _STR, "group": _STR}, "opt": {}},
    "tileset.from_atlas": {"req": {"path": _STR, "texture": _STR, "tile_size": (list,)},
                           "opt": {"margins": (list,), "separation": (list,), "collision": (str, list),
                                   "collision_layer": (int,)}},
    "tilemap.set_cells": {"req": {"path": _STR}, "opt": {"cells": (list,), "erase": (list,)}},
    "tilemap.fill_rect": {"req": {"path": _STR, "rect": (list,), "atlas": (list,)},
                          "opt": {"source": (int,), "alt": (int,)}},
    "spriteframes.from_sheet": {"req": {"path": _STR, "texture": _STR, "hframes": (int,), "vframes": (int,),
                                        "animations": (dict,)}, "opt": {"autoplay": _STR}},
    "animation.create": {"req": {"player": _STR, "name": _STR, "tracks": (list,)},
                         "opt": {"library": _STR, "length": _NUM, "step": _NUM, "loop": _STR,
                                 "replace": (bool,), "autoplay": (bool,)}},
}
# Fields whose value is a res:// file that must already exist in the project.
RES_REF_FIELDS = {"res", "script", "scene", "texture"}
NODE_PATH_FIELDS = {"parent", "path", "from", "to", "player"}
_NODE_PATH_RE = re.compile(r"^(\.|[^/\\:][^\\:]{0,510})$")


def load_catalog() -> dict[str, Any]:
    cat = C.read_json(CATALOG_PATH)
    classes = sorted({c for group in cat["node_classes"].values() for c in group})
    return {"classes": classes, "resources": sorted(set(cat["resource_classes"]))}


# ---------------------------------------------------------------- validation (before Godot)


def _type_ok(value: Any, types: tuple) -> bool:
    if isinstance(value, bool) and bool not in types:
        return False
    return isinstance(value, types)


def _walk_value(project: C.Project, value: Any, catalog: dict[str, Any], where: str, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise C.GamekitError("VALIDATION_FAILED", f"{where}: value nested deeper than {MAX_DEPTH}")
    if isinstance(value, float) and not math.isfinite(value):
        raise C.GamekitError("VALIDATION_FAILED", f"{where}: non-finite number")
    if isinstance(value, str) and len(value) > MAX_STRING:
        raise C.GamekitError("VALIDATION_FAILED", f"{where}: string longer than {MAX_STRING}")
    if isinstance(value, list):
        if len(value) > MAX_LIST:
            raise C.GamekitError("VALIDATION_FAILED", f"{where}: list longer than {MAX_LIST}")
        for i, item in enumerate(value):
            _walk_value(project, item, catalog, f"{where}[{i}]", depth + 1)
    if isinstance(value, dict):
        if "$res" in value:
            project.res_to_path(str(value["$res"]), must_exist=True)
        if "$type" in value and value["$type"] not in catalog["resources"]:
            raise C.GamekitError("VALIDATION_FAILED", f"{where}: resource class not in catalog: {value['$type']}")
        for k, v in value.items():
            if not isinstance(k, str) or len(k) > 200:
                raise C.GamekitError("VALIDATION_FAILED", f"{where}: bad key {k!r}")
            _walk_value(project, v, catalog, f"{where}.{k}", depth + 1)


def validate_ops(project: C.Project, ops: Any, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(ops, list):
        raise C.GamekitError("VALIDATION_FAILED", "ops must be a list")
    if len(ops) > MAX_OPS:
        raise C.GamekitError("VALIDATION_FAILED", f"at most {MAX_OPS} ops per command")
    for i, op in enumerate(ops):
        where = f"ops[{i}]"
        if not isinstance(op, dict) or op.get("op") not in OPS:
            raise C.GamekitError("VALIDATION_FAILED", f"{where}: unknown op {op.get('op') if isinstance(op, dict) else op!r}",
                                 known_ops=sorted(OPS))
        spec = OPS[op["op"]]
        for key, types in spec["req"].items():
            if key not in op or not _type_ok(op[key], types):
                raise C.GamekitError("VALIDATION_FAILED", f"{where} ({op['op']}): field {key!r} missing or wrong type")
        allowed = set(spec["req"]) | set(spec["opt"]) | {"op"}
        extra = set(op) - allowed
        if extra:
            raise C.GamekitError("VALIDATION_FAILED", f"{where} ({op['op']}): unknown fields {sorted(extra)}")
        for key, types in spec["opt"].items():
            if key in op and not _type_ok(op[key], types):
                raise C.GamekitError("VALIDATION_FAILED", f"{where} ({op['op']}): field {key!r} has wrong type")
        for key in NODE_PATH_FIELDS & set(op):
            if not _NODE_PATH_RE.match(op[key]) or op[key].startswith("/") or ".." in op[key].split("/"):
                raise C.GamekitError("VALIDATION_FAILED", f"{where}: bad node path {op[key]!r}")
        for key in RES_REF_FIELDS & set(op):
            project.res_to_path(op[key], must_exist=True)
        if op["op"] == "node.create" and op["type"] not in catalog["classes"]:
            raise C.GamekitError("VALIDATION_FAILED", f"{where}: node class not in catalog: {op['type']}")
        if op["op"] == "resource.new" and op["type"] not in catalog["resources"]:
            raise C.GamekitError("VALIDATION_FAILED", f"{where}: resource class not in catalog: {op['type']}")
        _walk_value(project, {k: v for k, v in op.items() if k != "op"}, catalog, where)
    return ops


# ---------------------------------------------------------------- import freshness


def _stamp(project_root: Path) -> Path:
    return project_root / ".godot" / "hhgk-import.stamp"


def import_is_stale(project_root: Path) -> bool:
    stamp = _stamp(project_root)
    if not (project_root / ".godot").is_dir() or not stamp.exists():
        return True
    stamp_time = stamp.stat().st_mtime
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in IMPORT_EXTS and ext != ".gd":
                continue
            full = os.path.join(dirpath, name)
            try:
                if os.path.getmtime(full) > stamp_time:
                    return True
            except OSError:
                continue
            if ext in IMPORT_EXTS and not os.path.exists(full + ".import"):
                return True
    return False


def refresh_import(project_root: Path, force: bool = False) -> dict[str, Any] | None:
    if not force and not import_is_stale(project_root):
        return None
    run = C.import_project(project_root)
    if run.timed_out or run.exit_code not in (0, None):
        raise C.GamekitError("GODOT_FAILED", "editor --import failed", process=run.summary(),
                             tail=(run.stdout + run.stderr)[-1500:])
    stamp = _stamp(project_root)
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(C.now_iso() + "\n", encoding="utf-8")
    return {"imported": True, **run.summary()}


# ---------------------------------------------------------------- compare and uid


def approx_equal(a: Any, b: Any, tol: float = 1e-5) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(approx_equal(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(approx_equal(x, y, tol) for x, y in zip(a, b))
    return a == b


def readback_mismatches(apply_result: dict[str, Any], readback: dict[str, Any]) -> list[str]:
    problems = []
    if not approx_equal(apply_result.get("state"), readback.get("state")):
        problems.append("scene state read back from disk differs from the applied state")
    probes = {(p["path"], p["prop"]): p for p in readback.get("probes", [])}
    for exp in apply_result.get("expected", []):
        got = probes.get((exp["path"], exp["prop"]))
        if got is None or got.get("missing"):
            problems.append(f"{exp['path']}:{exp['prop']} missing after reload")
        elif not approx_equal(exp["value"], got.get("value")):
            problems.append(f"{exp['path']}:{exp['prop']} is {got.get('value')!r}, expected {exp['value']!r}")
    return problems


_HEADER_RE = re.compile(rb"^\[gd_scene[^\]\n]*\]")
_UID_RE = re.compile(rb'uid="(uid://[a-z0-9]+)"')


def keep_uid(new: bytes, old: bytes | None) -> bytes:
    """ResourceSaver drops the uid when saving to a temp path; put the scene's original uid back."""
    if not old:
        return new
    old_header = _HEADER_RE.match(old)
    new_header = _HEADER_RE.match(new)
    if not old_header or not new_header:
        return new
    uid = _UID_RE.search(old_header.group(0))
    if not uid:
        return new
    header = new_header.group(0)
    if _UID_RE.search(header):
        header = _UID_RE.sub(b'uid="' + uid.group(1) + b'"', header)
    else:
        header = header[:-1] + b' uid="' + uid.group(1) + b'"]'
    return header + new[new_header.end():]


# ---------------------------------------------------------------- commands


def _scene_path(project: C.Project, scene: str) -> Path:
    if not scene.endswith(".tscn"):
        raise C.GamekitError("BAD_PATH", "gamekit edits text scenes (.tscn) only")
    return project.res_to_path(scene)


def inspect(project: C.Project, scene: str, timeout: float = 120.0) -> dict[str, Any]:
    _scene_path(project, scene)
    project.res_to_path(scene, must_exist=True)
    with C.project_lock(project, "scene.inspect", wait_seconds=30):
        refresh_import(project.root)
        run = C.run_godot_tool(project.root, "scene_tool.gd", {"mode": "inspect", "scene": scene}, timeout=timeout)
    result = C.require_result(run, "scene inspect")
    result["process"] = run.summary()
    return result


def apply(
    project: C.Project,
    scene: str,
    ops: list[dict[str, Any]],
    command_id: str,
    *,
    create: dict[str, Any] | None = None,
    expect_sha256: str | None = None,
    allow_open_editor: bool = False,
    timeout: float = 180.0,
) -> dict[str, Any]:
    C.validate_command_id(command_id)
    catalog = load_catalog()
    scene_path = _scene_path(project, scene)
    if create is not None:
        if not isinstance(create, dict) or create.get("root_type") not in catalog["classes"]:
            raise C.GamekitError("VALIDATION_FAILED", "create.root_type must be a catalog node class")
        _walk_value(project, create.get("props", {}), catalog, "create.props")
    validate_ops(project, ops, catalog)
    request_digest = C.digest({"kind": "scene.apply", "scene": scene, "ops": ops, "create": create})
    journal = C.Journal(project)
    with C.project_lock(project, "scene.apply", wait_seconds=30):
        prior = journal.replay_or_conflict(command_id, request_digest)
        if prior is not None:
            return prior
        if create is not None and scene_path.exists():
            raise C.GamekitError("CONFLICT", f"{scene} already exists; use scene apply")
        if create is None and not scene_path.is_file():
            raise C.GamekitError("NOT_FOUND", f"{scene} does not exist; use scene new")
        before = scene_path.read_bytes() if scene_path.exists() else None
        before_sha = C.sha256_bytes(before) if before is not None else None
        if expect_sha256 and expect_sha256 != before_sha:
            raise C.GamekitError("STALE", "scene changed since it was inspected", current_sha256=before_sha)
        C.refuse_if_editor_open(project, allow_open_editor)
        # ``scene new res://levels/intro/main.tscn`` should work on a fresh
        # project.  Godot writes the temporary scene beneath this directory,
        # so create the validated parent before launching it.
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        imported = refresh_import(project.root)
        temp_res = scene.rsplit("/", 1)[0] + f"/.{scene_path.stem}.hhtmp-{secrets.token_hex(3)}.tscn"
        temp_path = project.res_to_path(temp_res)
        request = {"mode": "apply", "scene": scene, "temp_out": temp_res, "create": create, "ops": ops,
                   "classes": catalog["classes"], "resources": catalog["resources"]}
        try:
            run = C.run_godot_tool(project.root, "scene_tool.gd", request, timeout=timeout)
            result = C.require_result(run, "scene apply")
            if not temp_path.is_file():
                raise C.GamekitError("GODOT_FAILED", "apply reported ok but wrote no temp scene")
            data = keep_uid(temp_path.read_bytes(), before)
            current = scene_path.read_bytes() if scene_path.exists() else None
            if current != before:
                raise C.GamekitError("STALE", "scene changed on disk while the apply ran; nothing written")
            C.checkpoint(project, command_id, [scene_path])
            C.atomic_write_bytes(scene_path, data)
        finally:
            if temp_path.exists():
                temp_path.unlink()
        probes = [{"path": e["path"], "prop": e["prop"]} for e in result.get("expected", [])]
        try:
            rb = C.run_godot_tool(project.root, "scene_tool.gd",
                                  {"mode": "readback", "scene": scene, "probes": probes}, timeout=timeout)
            readback = C.require_result(rb, "scene readback")
            problems = readback_mismatches(result, readback)
            if problems:
                raise C.GamekitError("READBACK_MISMATCH", "; ".join(problems[:5]), problems=problems[:40])
        except C.GamekitError:
            C.restore_checkpoint(project, command_id)
            raise
        after = scene_path.read_bytes()
        receipt = {
            "ok": True,
            "status": "COMMITTED",
            "kind": "scene.apply",
            "command_id": command_id,
            "project": project.project_id,
            "scene": scene,
            "created": create is not None,
            "ops": len(ops),
            "touched": result.get("touched", []),
            "before_sha256": before_sha,
            "after_sha256": C.sha256_bytes(after),
            "node_count": readback["state"].get("node_count"),
            "readback": "FRESH_PROCESS_MATCH",
            "import": imported,
            "apply_process": run.summary(),
            "readback_process": rb.summary(),
            "at": C.now_iso(),
        }
        journal.append(command_id, request_digest, receipt)
        return receipt


def undo(project: C.Project, command_id: str, *, allow_open_editor: bool = False) -> dict[str, Any]:
    """Undo one committed scene apply. The journal row is written only after readback."""
    C.validate_command_id(command_id)
    journal = C.Journal(project)
    undo_id = f"undo.{command_id}"[:96]
    request_digest = C.digest({"kind": "scene.undo", "of": command_id})
    with C.project_lock(project, "scene.undo", wait_seconds=30):
        prior = journal.replay_or_conflict(undo_id, request_digest)
        if prior is not None:
            return prior
        rec = journal.find(command_id)
        if rec is None or rec["receipt"].get("kind") != "scene.apply":
            raise C.GamekitError("NOT_FOUND", f"no committed scene.apply with command_id {command_id!r}")
        receipt = rec["receipt"]
        scene_path = project.res_to_path(receipt["scene"])
        current = C.sha256_file(scene_path) if scene_path.exists() else None
        if current != receipt["after_sha256"]:
            raise C.GamekitError("UNDO_CONFLICT", "scene changed after that command; undo newer commands first",
                                 current_sha256=current, expected_sha256=receipt["after_sha256"])
        C.refuse_if_editor_open(project, allow_open_editor)
        # Keep the live bytes under the undo id. A failed readback puts them back and writes no
        # journal row, so the same undo id can be retried.
        C.checkpoint(project, undo_id, [scene_path])
        restored: str | None = None
        try:
            C.restore_checkpoint(project, command_id)
            restored = C.sha256_file(scene_path) if scene_path.exists() else None
            if restored != receipt["before_sha256"]:
                raise C.GamekitError("STATE_CORRUPT", "restored bytes do not match the checkpoint")
            if restored is not None:
                rb = C.run_godot_tool(project.root, "scene_tool.gd", {"mode": "inspect", "scene": receipt["scene"]})
                C.require_result(rb, "undo readback")
        except Exception as original:
            try:
                C.restore_checkpoint(project, undo_id)
            except Exception as exc:
                raise C.GamekitError(
                    "STATE_CORRUPT",
                    f"undo failed ({original}) and the current scene could not be restored ({exc})",
                ) from original
            raise
        out = {"ok": True, "status": "UNDONE", "kind": "scene.undo", "command_id": undo_id, "undo_of": command_id,
               "scene": receipt["scene"], "sha256": restored, "at": C.now_iso()}
        journal.append(undo_id, request_digest, out)
        return out


def catalog_check(project: C.Project) -> dict[str, Any]:
    """Confirm every catalog class exists and is instantiable in the pinned Godot."""
    catalog = load_catalog()
    run = C.run_godot_tool(project.root, "scene_tool.gd", {"mode": "catalog", **catalog}, timeout=120)
    result = C.require_result(run, "catalog check")
    result["ok"] = not result.get("missing") and not result.get("wrong_kind")
    return result


def check(project: C.Project, timeout: float = 300.0) -> dict[str, Any]:
    with C.project_lock(project, "check", wait_seconds=30):
        imported = refresh_import(project.root)
        run = C.run_godot_tool(project.root, "scene_tool.gd", {"mode": "check"}, timeout=timeout)
    result = C.require_result(run, "project check")
    result["godot_errors"] = run.errors[:60]
    result["godot_warnings"] = run.warnings[:60]
    result["clean"] = bool(result.get("clean")) and not run.errors
    result["ok"] = result["clean"]
    result["import"] = imported
    return result


# ---------------------------------------------------------------- CLI


def _load_ops(path: str) -> list[dict[str, Any]]:
    safe = C.refuse_unsafe_host_path(Path(path), what="--ops")
    data = C.read_json(safe)
    if isinstance(data, dict):
        data = data.get("ops")
    if not isinstance(data, list):
        raise C.GamekitError("BAD_REQUEST", "ops file must be a list or {\"ops\": [...]}")
    return data


def _cmd_project_add(a: argparse.Namespace) -> dict[str, Any]:
    project = C.register_project(a.path, a.id)
    out = {"ok": True, **project.to_json()}
    if not a.no_import:
        with C.project_lock(project, "import", wait_seconds=30):
            out["import"] = refresh_import(project.root)
    return out


def _cmd_project_list(a: argparse.Namespace) -> dict[str, Any]:
    return {"ok": True, "projects": [p.to_json() for p in C.list_projects()]}


def _cmd_project_import(a: argparse.Namespace) -> dict[str, Any]:
    project = C.get_project(a.project)
    with C.project_lock(project, "import", wait_seconds=30):
        return {"ok": True, "import": refresh_import(project.root, force=True)}


def _cmd_inspect(a: argparse.Namespace) -> dict[str, Any]:
    out = inspect(C.get_project(a.project), a.scene)
    if a.sha:
        out["sha256"] = C.sha256_file(C.get_project(a.project).res_to_path(a.scene))
    return out


def _cmd_new(a: argparse.Namespace) -> dict[str, Any]:
    ops = _load_ops(a.ops) if a.ops else []
    props = C.parse_json_text(a.props) if a.props else {}
    create = {"root_type": a.root, "root_name": a.name or Path(a.scene).stem.title().replace("_", ""), "props": props}
    return apply(C.get_project(a.project), a.scene, ops, a.command_id, create=create,
                 allow_open_editor=a.allow_open_editor)


def _cmd_apply(a: argparse.Namespace) -> dict[str, Any]:
    ops = _load_ops(a.ops) if a.ops else C.parse_json_text(a.ops_json)
    return apply(C.get_project(a.project), a.scene, ops, a.command_id, expect_sha256=a.expect_sha256,
                 allow_open_editor=a.allow_open_editor)


def _cmd_undo(a: argparse.Namespace) -> dict[str, Any]:
    return undo(C.get_project(a.project), a.command_id, allow_open_editor=a.allow_open_editor)


def _cmd_ops(a: argparse.Namespace) -> dict[str, Any]:
    out = {"ok": True, "ops": {k: {"required": sorted(v["req"]), "optional": sorted(v["opt"])} for k, v in OPS.items()},
           "catalog": load_catalog()}
    if a.project:
        out["catalog_check"] = catalog_check(C.get_project(a.project))
        out["ok"] = out["catalog_check"]["ok"]
    return out


def _cmd_check(a: argparse.Namespace) -> dict[str, Any]:
    return check(C.get_project(a.project))


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("project", help="register / list / import game projects")
    ps = p.add_subparsers(dest="action", required=True)
    pa = ps.add_parser("add", help="register a Godot project folder (contains project.godot)")
    pa.add_argument("path")
    pa.add_argument("--id", default=None)
    pa.add_argument("--no-import", action="store_true")
    pa.set_defaults(func=_cmd_project_add)
    pl = ps.add_parser("list")
    pl.set_defaults(func=_cmd_project_list)
    pi = ps.add_parser("import", help="run the pinned editor --import pass")
    pi.add_argument("project")
    pi.set_defaults(func=_cmd_project_import)

    s = sub.add_parser("scene", help="inspect / new / apply / undo text scenes")
    ss = s.add_subparsers(dest="action", required=True)
    si = ss.add_parser("inspect")
    si.add_argument("project")
    si.add_argument("scene")
    si.add_argument("--sha", action="store_true", help="include the file sha256 for --expect-sha256")
    si.set_defaults(func=_cmd_inspect)
    sn = ss.add_parser("new", help="create a new scene with a root node (and optional ops)")
    sn.add_argument("project")
    sn.add_argument("scene")
    sn.add_argument("--root", required=True, help="root node class, e.g. Node2D, Node3D, Control")
    sn.add_argument("--name", default=None)
    sn.add_argument("--props", default=None, help="JSON object of root properties")
    sn.add_argument("--ops", default=None, help="JSON file with ops to apply after creating the root")
    sn.add_argument("--command-id", required=True)
    sn.add_argument("--allow-open-editor", action="store_true")
    sn.set_defaults(func=_cmd_new)
    sa = ss.add_parser("apply", help="apply ops (JSON list) to an existing scene")
    sa.add_argument("project")
    sa.add_argument("scene")
    g = sa.add_mutually_exclusive_group(required=True)
    g.add_argument("--ops", help="JSON file: [ops] or {\"ops\": [...]}")
    g.add_argument("--ops-json", help="inline JSON list of ops")
    sa.add_argument("--command-id", required=True)
    sa.add_argument("--expect-sha256", default=None)
    sa.add_argument("--allow-open-editor", action="store_true")
    sa.set_defaults(func=_cmd_apply)
    su = ss.add_parser("undo", help="restore the scene to before a committed command")
    su.add_argument("project")
    su.add_argument("--command-id", required=True)
    su.add_argument("--allow-open-editor", action="store_true")
    su.set_defaults(func=_cmd_undo)
    so = ss.add_parser("ops", help="list op kinds, fields and the class catalog")
    so.add_argument("--project", default=None, help="also check the catalog against the pinned Godot")
    so.set_defaults(func=_cmd_ops)

    c = sub.add_parser("check", help="load every script/scene/resource of a project and report problems")
    c.add_argument("project")
    c.set_defaults(func=_cmd_check)
