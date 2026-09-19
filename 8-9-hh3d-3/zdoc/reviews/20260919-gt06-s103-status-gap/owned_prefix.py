"""Owned S103 status-gap prefix planner (diagnostic-only).

The static path verifies the S102 fixture, source closure, profile, binary and
generated native overlay without starting Godot or a scheduler task.  The
existing campaign child is intentionally a fixed 35-batch acceptance runner;
this module therefore refuses to launch until a bounded child with equivalent
Stop/exit/cleanup accounting exists.  It prints a precise blocker report
instead of silently widening the diagnostic into a formal campaign.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
HH3D = HERE.parents[2]
STUDIO = HH3D / "studio"
FAILURE_ROOT = HERE / "failure" / "raw" / "run-00-attempt-01"
SOURCE_MANIFEST = FAILURE_ROOT / "source-files.json"
S102_PREFLIGHT_PATH = HERE.parent / "20260919-gt06-s102-observability" / "preflight.py"
NATIVE_PROBE_PATH = HERE / "native_probe.py"
NATIVE_SOURCE = STUDIO / "tests/replay/benchmark_native.gd"

SOURCE_CHECKPOINT = "56bfd448e83aa2512c0c2561e8e1a29f12134360"
SOURCE_CLOSURE_SHA256 = "7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467"
PROFILE_SHA256 = "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85"
NATIVE_SOURCE_SHA256 = "13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95"
GENERATED_OVERLAY_SHA256 = "bb137f32f1fae3730cc139f03fc6902813b3742d5a08d437e957e291cfe0ec46"
SOURCE_COUNT = 53
PREFLIGHT_HTTP_COMMANDS = 1000
PREFLIGHT_NATIVE_CYCLES = 100
PREFIX_BATCH_INDICES = tuple(range(7))
FULL_PROFILE_CYCLES = 100
STATUS_GAP_LIMIT_MS = 2000
OUTER_WALL_SECONDS = 1200

_RUN_ID = re.compile(r"gt06-s103-prefix-[a-z0-9][a-z0-9-]{0,47}\Z")


class OwnedPrefixError(ValueError):
    """A frozen input or bounded-run invariant is not satisfied."""


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise OwnedPrefixError(code)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path, cap: int = 256 * 1024 * 1024) -> bytes:
    _need(path.is_file() and not path.is_symlink(), "OWNED_FILE")
    raw = path.read_bytes()
    _need(0 < len(raw) <= cap, "OWNED_FILE_SIZE")
    return raw


def _closure(files: dict[str, str]) -> str:
    payload = "".join(name + "\0" + files[name] + "\n" for name in sorted(files))
    return sha(payload.encode("utf-8"))


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    _need(spec is not None and spec.loader is not None, "OWNED_MODULE_SPEC")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_s102() -> tuple[Any, Any, dict[str, bytes], dict[str, str], Any]:
    """Load the S102 fixture first, then obtain its dynamic source closure.

    ``preflight.load_campaign`` calls ``campaign.load_fixture()`` before
    ``campaign.source_files()``.  Keeping this call intact avoids accidentally
    hashing a partially imported or untrusted dependency set.
    """
    _need(S102_PREFLIGHT_PATH.is_file(), "OWNED_S102_PREFLIGHT_MISSING")
    preflight = _load_module(S102_PREFLIGHT_PATH, "s103_owned_s102_preflight")
    campaign, factory, trusted, sources = preflight.load_campaign(HH3D)
    return campaign, factory, trusted, sources, preflight


def frozen_source_manifest() -> dict[str, str]:
    value = json.loads(_read(SOURCE_MANIFEST, 128 * 1024))
    _need(type(value) is dict and len(value) == SOURCE_COUNT, "OWNED_SOURCE_COUNT")
    _need(all(type(k) is str and type(v) is str and re.fullmatch(r"[0-9a-f]{64}", v)
              for k, v in value.items()), "OWNED_SOURCE_SHAPE")
    value = dict(sorted(value.items()))
    _need(_closure(value) == SOURCE_CLOSURE_SHA256, "OWNED_SOURCE_CLOSURE")
    return value


def verify_pins() -> dict[str, Any]:
    """Verify the exact S102 source/profile/binary pins, without launching."""
    campaign, _factory, _trusted, sources, preflight = load_s102()
    frozen = frozen_source_manifest()
    _need(len(sources) == SOURCE_COUNT, "OWNED_SOURCE_COUNT")
    _need(sources == frozen, "OWNED_SOURCE_PIN_MISMATCH")
    _need(campaign.closure(sources) == SOURCE_CLOSURE_SHA256, "OWNED_SOURCE_CLOSURE")
    _need(campaign.profile.PROFILE_SHA256 == PROFILE_SHA256, "OWNED_PROFILE_PIN")
    _need(campaign.native_job.WALL_SECONDS == 20, "OWNED_NATIVE_WALL_CHANGED")
    checked = preflight.check()
    _need(checked[1] == sources, "OWNED_PREFLIGHT_SOURCE_MISMATCH")
    executable = Path(checked[2])
    check_report = checked[3]
    _need(check_report["godot_sha256"] == json.loads(_read(STUDIO / "toolchain.lock.json"))["godot"]["gui_sha256"],
          "OWNED_BINARY_PIN")
    _need(sha(_read(executable)) == check_report["godot_sha256"], "OWNED_BINARY_DRIFT")
    return {"campaign": campaign, "sources": sources, "executable": executable,
            "source_closure_sha256": SOURCE_CLOSURE_SHA256,
            "profile_sha256": PROFILE_SHA256, "godot_sha256": check_report["godot_sha256"],
            "python_sha256": check_report["python_sha256"],
            "preflight_helper_sha256": check_report["helper_sha256"]}


def generated_overlay() -> bytes:
    """Generate and verify the additive overlay entirely in memory."""
    raw = _read(NATIVE_SOURCE)
    _need(sha(raw) == NATIVE_SOURCE_SHA256, "OWNED_NATIVE_SOURCE_DRIFT")
    probe = _load_module(NATIVE_PROBE_PATH, "s103_owned_native_probe")
    _need(probe.SOURCE_SHA256 == NATIVE_SOURCE_SHA256, "OWNED_NATIVE_PROBE_PIN")
    overlay = probe.transform(raw)
    _need(sha(overlay) == GENERATED_OVERLAY_SHA256, "OWNED_OVERLAY_HASH")
    return overlay


def validate_run_id(run_id: str) -> str:
    _need(type(run_id) is str and _RUN_ID.fullmatch(run_id) is not None, "OWNED_RUN_ID")
    return run_id


def run_root(run_id: str) -> Path:
    validate_run_id(run_id)
    root = (HERE / "owned" / run_id).resolve()
    _need(root.is_relative_to(HERE.resolve()), "OWNED_ROOT_SCOPE")
    _need(not root.exists(), "OWNED_RUN_ROOT_EXISTS")
    return root


def plan(run_id: str = "gt06-s103-prefix-static") -> dict[str, Any]:
    validate_run_id(run_id)
    pins = verify_pins()
    overlay = generated_overlay()
    root = run_root(run_id)
    return {
        "schema_id": "hh-studio.gt06-s103-owned-prefix-plan",
        "schema_version": "1.0.0", "run_id": run_id,
        "source_checkpoint": SOURCE_CHECKPOINT,
        "source_file_count": SOURCE_COUNT,
        "source_closure_sha256": pins["source_closure_sha256"],
        "profile_sha256": pins["profile_sha256"],
        "godot_sha256": pins["godot_sha256"],
        "native_source_sha256": NATIVE_SOURCE_SHA256,
        "generated_overlay_sha256": sha(overlay), "generated_overlay_bytes": len(overlay),
        "preflight": {"exactly_one": True, "http_commands": PREFLIGHT_HTTP_COMMANDS,
                      "native_cycles": PREFLIGHT_NATIVE_CYCLES,
                      "original_native_wall_seconds": 20},
        "prefix": {"batch_indices": list(PREFIX_BATCH_INDICES),
                    "batch_count": len(PREFIX_BATCH_INDICES),
                    "cycles_per_batch": FULL_PROFILE_CYCLES,
                    "status_gap_limit_ms": STATUS_GAP_LIMIT_MS,
                    "outer_wall_seconds": OUTER_WALL_SECONDS,
                    "heartbeat_preserved": True},
        "formal_acceptance": False, "eligible_for_dataset": False,
        "fresh_empty_root": str(root),
        "launch": {"engine_started": False, "status": "BLOCKED_STATIC_ONLY"},
    }


def blocker_report(run_id: str) -> dict[str, Any]:
    """Explain why launch is refused instead of weakening campaign guarantees."""
    validate_run_id(run_id)
    return {
        "schema_id": "hh-studio.gt06-s103-owned-prefix-blocker",
        "schema_version": "1.0.0", "run_id": run_id,
        "status": "BLOCKED_STATIC_ONLY", "formal_acceptance": False,
        "eligible_for_dataset": False, "engine_started": False,
        "reason_code": "NO_SAFE_BOUNDED_CAMPAIGN_CHILD",
        "detail": ("run_benchmark_campaign.run_child is the frozen formal 35-batch "
                   "lifecycle; invoking it would exceed the 0..6 diagnostic bound. "
                   "A safe launch requires an equivalent bounded child with native "
                   "Stop, actual target/helper exits, and zero-tree cleanup receipts."),
        "required_before_launch": ["bounded child API", "fresh run root", "actual exits", "cleanup verification"],
        "source_closure_sha256": SOURCE_CLOSURE_SHA256, "profile_sha256": PROFILE_SHA256,
        "status_gap_limit_ms": STATUS_GAP_LIMIT_MS,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="gt06-s103-prefix-static")
    parser.add_argument("--check", action="store_true", help="verify frozen pins and generated overlay")
    parser.add_argument("--launch", action="store_true", help="emit blocker; never launches without bounded child")
    args = parser.parse_args(argv)
    if args.launch:
        value = blocker_report(args.run_id)
    else:
        value = plan(args.run_id)
        if not args.check:
            value["status"] = "STATIC_PLAN_ONLY"
    print(json.dumps(value, sort_keys=True))
    return 0 if not args.launch else 2


if __name__ == "__main__":
    raise SystemExit(main())
