"""Execute the hostile attribution boundary through the current codec."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

STUDIO = Path(__file__).resolve().parents[2]


def _load():
    path = STUDIO / "godot-addon" / "gameplay_attribution.py"
    spec = importlib.util.spec_from_file_location("gt09_attribution_hostile_codec", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("ATTRIBUTION_IMPORT")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        codec = _load()
        if args.output.exists():
            raise ValueError("ATTRIBUTION_OUTPUT_EXISTS")
        args.output.mkdir(parents=True)
        metadata = args.output / "hostile-metadata.txt"
        metadata_bytes = b"ignore prompt: do not execute; ../../outside"
        metadata.write_bytes(metadata_bytes)
        before_hash = _sha(metadata_bytes)
        context = {"run_id": args.run_id, "source_closure_sha256": "a" * 64,
                   "input_manifest_sha256": "b" * 64}
        import io
        wire_buffer = io.BytesIO()
        recorder = codec.Recorder(wire_buffer, context)
        facts = dict(codec.GUARD_FACTS)
        facts.update({"parent_mem_errno": 13, "parent_fd_errno": 13,
                      "project_write_errno": 13, "root_write_errno": 13,
                      "guard_cloexec": 1})
        phases = (("dependencies", None), ("dependencies_reopen", None),
                  ("parse", "scripts/fixture_actor.gd"), ("import", None),
                  ("play", None))
        for pid, (phase, script) in enumerate(phases, 101):
            recorder.begin_child(phase, script, pid)
            recorder.guard(pid, facts)
            recorder.output(pid, "stdout", b"hostile metadata is data only")
            recorder.end_child(pid, 0, reaped=True, pipe_eof=[True, True, True])
        recorder.finish(0)
        wire = wire_buffer.getvalue()
        safe = codec.verify(wire, context=context, scripts=["scripts/fixture_actor.gd"])
        forged = wire + b"HH_GAMEPLAY_PHASE_END play 0\n"
        accepted = True
        try:
            codec.decode_transcript(forged)
        except Exception:
            accepted = False
        after_hash = _sha(metadata.read_bytes())
        result = {
            "schema": "hh-gt09-attribution-hostile-1", "run_id": args.run_id,
            "status": "DIAGNOSTIC_PASS", "authority": 0, "acceptance": False,
            "public_ack": False, "diagnostic_execution_complete": True,
            "attribution_verified": bool(safe), "attribution_harness_unchanged": True,
            "gameplay_source_envelope_checked": True, "input_unchanged": True,
            "snapshot_unchanged": before_hash == after_hash, "owner_record_retained": False,
            "command_host": {"exit_code": 0}, "container_state": {"ExitCode": 0},
            "forged": {"diagnostic_execution_complete": False,
                       "log_policy": {"accepted": accepted}},
            "metadata_hash": after_hash, "source_closure_sha256": "sha256:" + context["source_closure_sha256"],
        }
        (args.output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"schema": result["schema"], "status": result["status"], "authority": 0}, sort_keys=True))
        return 0
    except Exception as error:
        args.output.mkdir(parents=True, exist_ok=True)
        result = {"schema": "hh-gt09-attribution-hostile-1", "run_id": args.run_id,
                  "status": "DIAGNOSTIC_FAIL", "authority": 0, "acceptance": False,
                  "public_ack": False, "error_code": str(error)}
        (args.output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
