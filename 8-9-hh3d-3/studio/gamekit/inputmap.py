"""hh input: list and replace InputMap actions stored in a game's project.godot.

``input set`` validates on the host, asks Godot to reject unknown keys before it writes, checkpoints
``project.godot``, swaps in the temp file Godot saved, and journals the command only after a fresh
process lists the same actions back.
"""

from __future__ import annotations

import argparse
import math
import re
import secrets
from pathlib import Path
from typing import Any

from . import common as C

MAX_ACTIONS = 128
MAX_EVENTS = 16
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_UI_PREFIX = "ui_"


def _is_ui(name: str) -> bool:
    return name.startswith(_UI_PREFIX)


def _fail(detail: str) -> None:
    raise C.GamekitError("VALIDATION_FAILED", detail)


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _fail(f"{where} must be a finite number")
    return float(value)


def _integer(value: Any, where: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{where} must be an integer {lo}..{hi}")
    number = float(value)
    if not number.is_integer():
        _fail(f"{where} must be an integer {lo}..{hi}")
    out = int(number)
    if out < lo or out > hi:
        _fail(f"{where} must be an integer {lo}..{hi}")
    return out


def validate_event(event: Any, where: str) -> dict[str, Any]:
    """Return one canonical event dict, or raise VALIDATION_FAILED. Key existence is checked in Godot."""
    if not isinstance(event, dict):
        _fail(f"{where} must be an object")
    keys = set(event)
    if keys == {"key"}:
        if not isinstance(event["key"], str) or not event["key"].strip() or len(event["key"]) > 64:
            _fail(f"{where} key must be a non-empty name")
        return {"key": event["key"].strip()}
    if keys == {"physical_key"}:
        if not isinstance(event["physical_key"], str) or not event["physical_key"].strip() or len(event["physical_key"]) > 64:
            _fail(f"{where} physical_key must be a non-empty name")
        return {"physical_key": event["physical_key"].strip()}
    if keys == {"joy_button"}:
        return {"joy_button": _integer(event["joy_button"], f"{where} joy_button", 0, 127)}
    if keys == {"joy_axis", "value"}:
        axis = _integer(event["joy_axis"], f"{where} joy_axis", 0, 9)
        value = _number(event["value"], f"{where} value")
        if value == 0.0 or value < -1.0 or value > 1.0:
            _fail(f"{where} joy axis value must be non-zero and from -1 to 1")
        return {"joy_axis": axis, "value": value}
    if keys == {"mouse_button"}:
        return {"mouse_button": _integer(event["mouse_button"], f"{where} mouse_button", 1, 9)}
    _fail(f"{where} must be one of key, physical_key, joy_button, joy_axis+value, mouse_button")
    return {}


def validate_actions(actions: Any) -> dict[str, dict[str, Any]]:
    """Host-side shape check. Returns a normalized copy (deadzone filled, events canonical)."""
    if not isinstance(actions, dict):
        _fail("actions must be an object of name -> {deadzone, events}")
    if len(actions) > MAX_ACTIONS:
        _fail(f"at most {MAX_ACTIONS} actions")
    out: dict[str, dict[str, Any]] = {}
    for name, spec in actions.items():
        if not isinstance(name, str) or not _NAME_RE.match(name):
            _fail(f"bad action name {name!r}")
        if not isinstance(spec, dict):
            _fail(f"{name} must be an object")
        extra = set(spec) - {"deadzone", "events"}
        if extra:
            _fail(f"{name} has unknown fields {sorted(extra)}")
        deadzone = 0.5 if "deadzone" not in spec else _number(spec["deadzone"], f"{name} deadzone")
        if deadzone < 0.0 or deadzone > 1.0:
            _fail(f"{name} deadzone must be from 0 to 1")
        raw_events = spec.get("events", [])
        if not isinstance(raw_events, list):
            _fail(f"{name} events must be a list")
        if len(raw_events) > MAX_EVENTS:
            _fail(f"{name} has more than {MAX_EVENTS} events")
        events = [validate_event(event, f"{name} events[{i}]") for i, event in enumerate(raw_events)]
        out[name] = {"deadzone": deadzone, "events": events}
    return out


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= 1e-5
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _events_semantic(requested: list[dict[str, Any]], written: Any) -> bool:
    if not isinstance(written, list) or len(requested) != len(written):
        return False
    for req, got in zip(requested, written):
        if not isinstance(got, dict) or set(req) != set(got):
            return False
        for field, value in req.items():
            other = got[field]
            if field in ("key", "physical_key"):
                if str(value).lower() != str(other).lower():
                    return False
            elif not _same(value, other):
                return False
    return True


def diff_request(requested: dict[str, dict[str, Any]], written: list[dict[str, Any]]) -> list[str]:
    """Canonical Godot echo of the request must describe the same actions the host asked for."""
    problems = []
    written_map = {str(item.get("name")): item for item in written if isinstance(item, dict)}
    if set(written_map) != set(requested):
        problems.append(f"tool wrote {sorted(written_map)}, request was {sorted(requested)}")
    for name, spec in requested.items():
        got = written_map.get(name)
        if not isinstance(got, dict):
            continue
        if not _same(spec["deadzone"], got.get("deadzone")):
            problems.append(f"{name} deadzone is {got.get('deadzone')!r}, expected {spec['deadzone']!r}")
        if not _events_semantic(spec["events"], got.get("events")):
            problems.append(f"{name} events are {got.get('events')!r}, expected {spec['events']!r}")
    return problems


def diff_readback(before: list[dict[str, Any]], written: list[dict[str, Any]], fresh: list[dict[str, Any]], replace: bool) -> list[str]:
    """Fresh process listing must equal the request, keeping or dropping other non-ui actions."""
    problems = []
    before_map = {str(item["name"]): item for item in before if isinstance(item, dict) and not _is_ui(str(item.get("name", "")))}
    written_map = {str(item["name"]): item for item in written if isinstance(item, dict) and item.get("name")}
    fresh_map = {str(item["name"]): item for item in fresh if isinstance(item, dict) and item.get("name")}
    fresh_relevant = {name: item for name, item in fresh_map.items() if not _is_ui(name) or name in written_map}
    expected = set(written_map) if replace else set(before_map) | set(written_map)
    if set(fresh_relevant) != expected:
        missing = sorted(expected - set(fresh_relevant))
        extra = sorted(set(fresh_relevant) - expected)
        problems.append(f"action set mismatch missing={missing} extra={extra}")
    for name in sorted(expected):
        want = written_map.get(name, before_map.get(name))
        got = fresh_relevant.get(name)
        if want is None or got is None:
            continue
        if not _same(want.get("deadzone"), got.get("deadzone")):
            problems.append(f"{name} deadzone read back {got.get('deadzone')!r}, expected {want.get('deadzone')!r}")
        if not _same(want.get("events"), got.get("events")):
            problems.append(f"{name} events read back {got.get('events')!r}, expected {want.get('events')!r}")
    return problems


def _coerce_actions(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise C.GamekitError("GODOT_FAILED", "action list missing from Godot result")
    out = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise C.GamekitError("GODOT_FAILED", "malformed action from Godot")
        out.append(item)
    out.sort(key=lambda item: item["name"])
    return out


def _file_has_action(data: bytes, action: str) -> bool:
    needle = action.encode("utf-8") + b"="
    return any(line.strip().startswith(needle) for line in data.splitlines())


def _list(project: C.Project, include_all: bool, timeout: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run = C.run_godot_tool(project.root, "inputmap_tool.gd", {"mode": "list", "all": include_all}, timeout=timeout)
    result = C.require_result(run, "input list")
    return _coerce_actions(result.get("actions")), run.summary()


def list_actions(project: C.Project, include_all: bool = False, timeout: float = 120.0) -> dict[str, Any]:
    with C.project_lock(project, "input.list", wait_seconds=30):
        actions, summary = _list(project, include_all, timeout)
    return {"ok": True, "project": project.project_id, "actions": actions, "count": len(actions), "process": summary}


def set_actions(
    project: C.Project,
    actions: Any,
    command_id: str,
    *,
    replace: bool = False,
    allow_open_editor: bool = False,
    timeout: float = 120.0,
) -> dict[str, Any]:
    command_id = C.validate_command_id(command_id)
    normalized = validate_actions(actions)
    request_digest = C.digest({"kind": "input.set", "actions": normalized, "replace": bool(replace)})
    journal = C.Journal(project)
    godot_file = project.root / "project.godot"
    temp = project.root / f"hh_input_tmp_{secrets.token_hex(4)}.godot"
    try:
        with C.project_lock(project, "input.set", wait_seconds=30):
            prior = journal.replay_or_conflict(command_id, request_digest)
            if prior is not None:
                return prior
            C.refuse_if_editor_open(project, allow_open_editor)
            before_sha = C.sha256_file(godot_file)
            C.checkpoint(project, command_id, [godot_file])
            try:
                run = C.run_godot_tool(
                    project.root,
                    "inputmap_tool.gd",
                    {"mode": "apply", "actions": normalized, "replace": bool(replace), "temp_out": temp.as_posix()},
                    timeout=timeout,
                )
                if C.sha256_file(godot_file) != before_sha:
                    raise C.GamekitError("GODOT_FAILED", "input tool modified project.godot directly")
                applied = C.require_result(run, "input set")
                if not temp.is_file():
                    raise C.GamekitError("GODOT_FAILED", "input set reported ok but wrote no project file")
                data = temp.read_bytes()
                before = _coerce_actions(applied.get("before"))
                written = _coerce_actions(applied.get("written"))
                echo = diff_request(normalized, written)
                if echo:
                    raise C.GamekitError("GODOT_FAILED", "; ".join(echo[:6]), problems=echo[:40])
                missing = [item["name"] for item in written if not _file_has_action(data, item["name"])]
                if b"config_version=" not in data or b"[application]" not in data or missing:
                    raise C.GamekitError("GODOT_FAILED", "saved project file failed host checks", missing=missing)
                C.atomic_write_bytes(godot_file, data)
                temp.unlink()
                fresh, fresh_summary = _list(project, True, timeout)
                problems = diff_readback(before, written, fresh, bool(replace))
                if problems:
                    raise C.GamekitError("READBACK_MISMATCH", "; ".join(problems[:6]), problems=problems[:40])
            except C.GamekitError:
                C.restore_checkpoint(project, command_id)
                raise
            receipt = {
                "ok": True,
                "status": "COMMITTED",
                "kind": "input.set",
                "command_id": command_id,
                "project": project.project_id,
                "replace": bool(replace),
                "actions": [item for item in fresh if not _is_ui(str(item["name"]))],
                "before_sha256": before_sha,
                "after_sha256": C.sha256_file(godot_file),
                "readback": "FRESH_PROCESS_MATCH",
                "apply_process": run.summary(),
                "readback_process": fresh_summary,
                "at": C.now_iso(),
            }
            journal.append(command_id, request_digest, receipt)
            return receipt
    finally:
        if temp.exists():
            temp.unlink()


def _load_actions(path: str) -> Any:
    data = C.read_json(Path(path))
    if not isinstance(data, dict):
        raise C.GamekitError("BAD_REQUEST", "actions file must be a JSON object")
    return data


def _cmd_list(args: argparse.Namespace) -> dict[str, Any]:
    return list_actions(C.get_project(args.project), include_all=args.include_all)


def _cmd_set(args: argparse.Namespace) -> dict[str, Any]:
    return set_actions(
        C.get_project(args.project),
        _load_actions(args.actions),
        args.command_id,
        replace=args.replace,
        allow_open_editor=args.allow_open_editor,
    )


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("input", help="list and set InputMap actions")
    commands = parser.add_subparsers(dest="action", required=True)
    listing = commands.add_parser("list", help="list input actions (ui_* only with --all)")
    listing.add_argument("project")
    listing.add_argument("--all", action="store_true", dest="include_all", help="include built-in ui_* actions")
    listing.set_defaults(func=_cmd_list)
    setting = commands.add_parser("set", help="replace the listed actions and save project.godot")
    setting.add_argument("project")
    setting.add_argument("--actions", required=True, help="JSON object of action name -> {deadzone, events}")
    setting.add_argument("--command-id", required=True)
    setting.add_argument("--replace", action="store_true", help="remove non-ui actions that are not listed")
    setting.add_argument("--allow-open-editor", action="store_true")
    setting.set_defaults(func=_cmd_set)
