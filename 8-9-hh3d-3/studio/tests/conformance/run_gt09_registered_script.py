"""Native K3 registered controller-source route diagnostic.

This runner uses the fixture host registration, ``RegisteredScriptRoute`` and
the durable gameplay-source owner.  It deliberately keeps the scene route and
source route separate: a typed source request is admitted by the registered
profile, dispatched once through the pinned Linux/Godot executor, and then
reconciled from the owner's journal.  The same fixed fixture input is replayed
against the repaired/published source and its postcondition is read back from
the native marker.

The output is authority-zero diagnostic evidence.  It is suitable as a K3
row only when the caller independently checks every raw process receipt,
source closure and the route envelope hash.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def _load(name: str, relative: str):
    path = STUDIO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("REGISTERED_SCRIPT_IMPORT")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_OWNER = _load("gt09_registered_script_owner", "godot-addon/gameplay_source_owner.py")
_ADAPTER = _load("gt09_registered_script_adapter", "godot-addon/gameplay_source_adapter.py")
_REGISTERED = _load("gt09_registered_script_registered_owner",
                    "godot-addon/registered_authoring_owner.py")
_FIXTURES = _load("gt09_registered_script_fixtures", "tests/godot/linux_probe_fixtures.py")
_PROBE = _load("gt09_registered_script_probe", "tests/godot/run_linux_probe.py")

SCHEMA = "hh-gt09-registered-script-result-1"
RUN_RE = re.compile(r"gt09-registered-script-[a-z0-9-]{1,48}\Z")
PROJECT = "project.registered.room"


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _case(speed: float) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Create one immutable room fixture source variant."""
    # The compact room controller has no generated asset dependency.  This
    # keeps the K3/K9 proof focused on the registered source route while the
    # separate GT09 publication rows cover Blender asset mounting.
    base = _FIXTURES.FIXTURES["gameplay_source_room_3d"]
    script = base["script"]
    # This field is an observable controller reaction.  The value is authored
    # in the script and emitted by the native fixture, so it cannot be inferred
    # from the caller's metadata.
    needle = "var topology_components: Dictionary = {}"
    if needle in script:
        script = script.replace(needle, needle + "\nvar controller_speed: float = %.6f" % speed, 1)
    else:
        script = script.replace("func _ready() -> void:",
                                "var controller_speed: float = %.6f\n\nfunc _ready() -> void:" % speed, 1)
    script = script.replace("avatar.z += 0.5", "avatar.z += controller_speed", 1)
    if 'var state := {"ticks": tick,' in script:
        script = script.replace('var state := {"ticks": tick,',
                                'var state := {"ticks": tick, "controller_speed": controller_speed,', 1)
    else:
        script = script.replace('var state := {"ticks": 12,',
                                'var state := {"ticks": 12, "controller_speed": controller_speed,', 1)
    expected = _copy(base["expected_state"])
    expected["controller_speed"] = speed
    expected["avatar_z"] = speed * 12.0
    case = {**base, "script": script, "expected_state": expected,
            "scene": _FIXTURES.SCENE,
            "project": _OWNER._load("gameplay_source_profile").PROJECT_TEMPLATE}
    # Registered source publication is an authenticated gameplay route.  Give
    # its native Godot startup the same bounded 30 s envelope as AUTH-03 so a
    # Docker cold start cannot consume the legacy 20 s attach window.
    case["timeout"] = 30
    case["authenticated_timeout"] = True
    values = _PROBE.case_files(case)
    values.pop("project.godot", None)
    return case, values


def _binding(run_id: str, closure: str, source_files: dict[str, str]) -> dict[str, Any]:
    files = dict(source_files)
    for relative in ("godot-addon/linux_executor.py",
                     "godot-addon/gameplay_sandbox.py",
                     "godot-addon/gameplay_source_profile.py"):
        files[relative] = hashlib.sha256((STUDIO / relative).read_bytes()).hexdigest()
    return {"run_id": run_id, "source_closure_sha256": closure,
            "authority": 0, "public_ack": False, "files": files}


def _run_native(*, case: dict[str, Any], files: dict[str, bytes], output: Path,
                run_id: str, closure: str, source_manifest: dict[str, str]) -> dict[str, Any]:
    if output.exists():
        raise RuntimeError("REGISTERED_SCRIPT_OUTPUT_EXISTS")
    project = output.parent / (output.name + "-project")
    project.mkdir(parents=True)
    for name, raw in {"project.godot": case["project"].encode(),
                      "scenes/fixture.tscn": case["scene"].encode(),
                      "scripts/fixture_actor.gd": case["script"].encode(),
                      **{name: raw for name, raw in files.items()
                         if name not in ("project.godot", "scenes/fixture.tscn", "scripts/fixture_actor.gd")}}.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    os.environ.setdefault("HH_STUDIO_LINUX_GODOT", str(
        STUDIO / ".local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64"))
    executor = _OWNER._load("linux_executor")
    observed = executor.run(project, mode=case["mode"], output=output,
                            timeout_seconds=case["timeout"],
                            source_closure_sha256=closure,
                            authenticated=bool(case.get("authenticated_timeout")))
    row = _PROBE.case_observation(output, case, name="gameplay_source_room_3d",
                                  binding=_binding(run_id, closure, source_manifest))
    row["native_result_sha256"] = hashlib.sha256((output / "result.json").read_bytes()).hexdigest()
    row["native_process_exit"] = json.loads((output / "result.json").read_text()).get("command_host", {})
    return row


def _request(*, command_id: str, expected: str, profile: Any,
             source: dict[str, bytes], lease: Any) -> dict[str, Any]:
    def encode(raw: bytes):
        # The registered adapter already supports canonical base64 chunks.
        # Preserve the protocol's 16 KiB string ceiling for real K8 assets.
        chunks = [base64.b64encode(raw[i:i + 12288]).decode('ascii')
                  for i in range(0, len(raw), 12288)]
        return chunks[0] if len(chunks) == 1 else chunks
    payload = {"profile": _REGISTERED.PROFILE, "profile_version": profile.version,
               "profile_digest": profile.as_dict()["catalog_digest"],
               "entrypoint": _OWNER.ENTRYPOINT,
               "expected_project_revision": expected,
               "source_files": {name: encode(raw)
                                for name, raw in sorted(source.items())}}
    return {"command_id": command_id, "schema_version": "hh-studio-0.1",
            "project_id": profile.project_id, "operation": "gameplay-source.publish",
            "lease_id": lease.lease_id, "fencing_epoch": lease.fencing_epoch,
            "expected_revision": expected, "target": {"path": _OWNER.ENTRYPOINT},
            "payload": payload,
            "payload_hash": "sha256:" + hashlib.sha256(
                _ADAPTER.canonical_bytes(payload)).hexdigest(),
            "deadline_ms": lease.expires_ms}


def run(*, run_id: str, output: Path) -> dict[str, Any]:
    if RUN_RE.fullmatch(run_id) is None:
        raise ValueError("REGISTERED_SCRIPT_RUN_ID")
    output = output.resolve()
    if output.exists():
        raise ValueError("REGISTERED_SCRIPT_OUTPUT_EXISTS")
    output.mkdir(parents=True)
    source_files, closure = _OWNER.runtime_source_closure()
    # K3 baseline and changed source use the same deterministic input trace.
    baseline_case, baseline_files = _case(0.5)
    changed_case, changed_files = _case(0.75)
    baseline = _run_native(case=baseline_case, files=baseline_files,
                           output=output / "baseline", run_id=run_id + "-baseline",
                           closure=closure, source_manifest=source_files)
    if baseline.get("fixture_observed") is not True:
        raise RuntimeError("REGISTERED_SCRIPT_BASELINE_NOT_OBSERVED")

    owner_parent = output / "owner-parent"
    owner_parent.mkdir()
    source_owner = _OWNER.GameplaySourcePublicationOwner.create(
        owner_parent, project_id=PROJECT, source_files=baseline_files,
        entrypoint=_OWNER.ENTRYPOINT, source_closure_sha256=closure)
    credential = source_owner.issue()
    grant = source_owner.authorize("Bearer " + credential.bearer, "scene.save")
    lease = source_owner.lease(grant)
    profile = _REGISTERED.load_fixture_host_profile(PROJECT)
    admission = _REGISTERED.make_admission(
        project_id=PROJECT, revision="sha256:" + "a" * 64,
        project_revision=source_owner.inspect()["project_revision"],
        lease_id=lease.lease_id, fencing_epoch=lease.fencing_epoch)
    handoff = _REGISTERED.BlenderHandoff("registered://script", "0" * 64,
                                         "0" * 64, "DIAGNOSTIC", "script-handoff")
    registered_owner = _REGISTERED.RegisteredAuthoringOwner(
        admission=admission, blender=handoff,
        native_apply=lambda *_args: (_ for _ in ()).throw(
            RuntimeError("REGISTERED_SCENE_ROUTE_NOT_USED")))
    adapter = _ADAPTER.GameplaySourceAdapter(source_owner, host_profile=profile)
    route = _REGISTERED.RegisteredScriptRoute(
        registered_owner, adapter=adapter, grant=grant, lease=lease,
        host_profile=profile)
    request = _request(command_id="registered.script.k3", expected=admission.project_revision,
                       profile=profile, source=changed_files, lease=lease)
    receipt = route.execute(request)
    retry = route.execute(request)
    if retry != receipt:
        raise RuntimeError("REGISTERED_SCRIPT_RETRY_CHANGED")
    repaired = _run_native(case=changed_case, files=changed_files,
                           output=output / "replay", run_id=run_id + "-replay",
                           closure=closure, source_manifest=source_files)
    if repaired.get("fixture_observed") is not True:
        raise RuntimeError("REGISTERED_SCRIPT_REPLAY_NOT_OBSERVED")
    before_state = baseline.get("untrusted_child_observation")
    after_state = repaired.get("untrusted_child_observation")
    if before_state == after_state:
        raise RuntimeError("REGISTERED_SCRIPT_BEHAVIOR_UNCHANGED")
    if after_state.get("controller_speed") != 0.75:
        raise RuntimeError("REGISTERED_SCRIPT_REACTION_READBACK_MISSING")
    result = {"schema": SCHEMA, "run_id": run_id, "fixture": "room_controller_diagnostic",
              "authority": 0, "public_ack": False, "status": "DIAGNOSTIC_PASS",
              "acceptance": False, "source_closure_sha256": closure,
              "registered_route": receipt, "same_command_retry": True,
              "baseline": baseline, "replay": repaired,
              "behavior_changed": before_state != after_state,
              "controller_reaction_readback": after_state.get("controller_speed") == 0.75,
              "native_run_count": 3}
    _write(output / "result.json", result)
    _write(output / "route-receipt.json", receipt)
    registered_owner.close()
    source_owner.close()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        result = {"schema": SCHEMA, "run_id": args.run_id, "authority": 0,
                  "public_ack": False, "status": "DRY_RUN",
                  "acceptance": False, "engine_launched": False,
                  "registered_route": _REGISTERED.SCRIPT_ROUTE_SCHEMA}
        print(json.dumps(result, sort_keys=True))
        return 0
    try:
        report = run(run_id=args.run_id, output=args.output)
    except Exception as error:
        detail = str(error).strip()
        # Keep a bounded, path-free diagnostic detail in authority-zero output.
        # The previous type-only ``ValueError`` made a boundary failure
        # indistinguishable from a malformed fixture and forced a rerun with
        # a traceback.  Never include credentials or arbitrary host paths.
        if len(detail) > 160 or "\\" in detail or "/" in detail:
            detail = type(error).__name__
        result = {"schema": SCHEMA, "run_id": args.run_id, "authority": 0,
                  "public_ack": False, "status": "DIAGNOSTIC_FAIL",
                  "acceptance": False, "error_code": str(error)
                  if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", str(error))
                  else type(error).__name__, "error_detail": detail}
        if args.output:
            args.output.mkdir(parents=True, exist_ok=True)
            _write(args.output / "result.json", result)
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps({"schema": SCHEMA, "run_id": args.run_id,
                      "status": report["status"], "authority": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
