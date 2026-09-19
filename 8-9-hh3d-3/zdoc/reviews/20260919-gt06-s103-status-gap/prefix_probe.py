"""S103 bounded native status-gap prefix (diagnostic only).

This module is deliberately inert on import.  It freezes the S102 53-file
closure, builds a disposable project containing the additive S103 native
overlay, and exposes a plan for one preflight followed by batches 0..6.  The
future launcher is documented in ``README-prefix.md``; this file does not
start Godot, a scheduler task, or the formal campaign.

The generated plugin is written below a fresh evidence root.  The checked-in
``studio/`` tree and the S102 failure packet are never modified.  Source and
profile pins, workload counts, heartbeat limits, and the formal acceptance
gate remain unchanged; every result from this prefix is explicitly ineligible
for acceptance or the F13/F14 dataset.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Any


HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[2] / "studio"
FAILURE_ROOT = HERE / "failure" / "raw" / "run-00-attempt-01"
SOURCE53_MANIFEST = FAILURE_ROOT / "source-files.json"

SOURCE_CHECKPOINT = "56bfd448e83aa2512c0c2561e8e1a29f12134360"
SOURCE_CLOSURE_SHA256 = "7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467"
PROFILE_SHA256 = "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85"
NATIVE_SOURCE_SHA256 = "13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95"

PREFLIGHT_HTTP_COMMANDS = 1000
PREFLIGHT_NATIVE_CYCLES = 100
MAX_PREFIX_BATCHES = 7
PREFIX_BATCH_INDICES = tuple(range(MAX_PREFIX_BATCHES))
OUTER_WALL_SECONDS = 1200
FORMAL_ACCEPTANCE = False
FULL_PROFILE_BATCHES = 35
FULL_PROFILE_CYCLES = 100
STATUS_GAP_LIMIT_MS = 2000

_ID = re.compile(r"gt06-s103-[a-z0-9-]{1,40}")


class PrefixError(ValueError):
    """A frozen input, overlay, or plan invariant is not satisfied."""


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise PrefixError(code)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def closure(files: dict[str, str]) -> str:
    return sha("".join(name + "\0" + files[name] + "\n"
                       for name in sorted(files)).encode("utf-8"))


def _read_regular(path: Path, cap: int = 256 * 1024 * 1024) -> bytes:
    _need(path.is_file() and not path.is_symlink(), "PREFIX_FILE")
    raw = path.read_bytes()
    _need(0 < len(raw) <= cap, "PREFIX_FILE_SIZE")
    return raw


def source53_manifest() -> dict[str, str]:
    """Read the immutable S102 map and require exactly the pinned 53 files."""
    value = json.loads(_read_regular(SOURCE53_MANIFEST, 128 * 1024))
    _need(type(value) is dict and len(value) == 53, "PREFIX_SOURCE53_COUNT")
    _need(all(type(k) is str and type(v) is str and re.fullmatch(r"[0-9a-f]{64}", v)
              for k, v in value.items()), "PREFIX_SOURCE53_SHAPE")
    frozen = dict(sorted(value.items()))
    _need(closure(frozen) == SOURCE_CLOSURE_SHA256, "PREFIX_SOURCE53_CLOSURE")
    return frozen


def verify_source53() -> dict[str, str]:
    """Hash the live tree against source53 without launching any process."""
    frozen = source53_manifest()
    for relative, expected in frozen.items():
        actual = sha(_read_regular(STUDIO / relative))
        _need(actual == expected, "PREFIX_SOURCE53_DRIFT")
    return frozen


def _load_native_probe():
    path = HERE / "native_probe.py"
    spec = importlib.util.spec_from_file_location("s103_prefix_native_probe", path)
    _need(spec is not None and spec.loader is not None, "PREFIX_PROBE_IMPORT")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _need(module.SOURCE_SHA256 == NATIVE_SOURCE_SHA256, "PREFIX_NATIVE_PIN")
    return module


def generated_native_overlay(raw: bytes | None = None) -> bytes:
    """Return the exact additive overlay bytes; never writes or mutates input."""
    if raw is None:
        raw = _read_regular(STUDIO / "tests/replay/benchmark_native.gd")
    _need(sha(raw) == NATIVE_SOURCE_SHA256, "PREFIX_NATIVE_SOURCE_DRIFT")
    return _load_native_probe().transform(raw)


def write_generated_overlay(project: Path) -> dict[str, str]:
    """Install the generated plugin into a disposable project and read it back."""
    destination = project / "addons/hh_benchmark/benchmark_native.gd"
    _need(destination.is_file(), "PREFIX_PROJECT_NATIVE_MISSING")
    overlay = generated_native_overlay()
    temporary = destination.with_suffix(destination.suffix + ".s103.tmp")
    _need(not temporary.exists(), "PREFIX_OVERLAY_TEMP_EXISTS")
    temporary.write_bytes(overlay)
    temporary.replace(destination)
    _need(destination.read_bytes() == overlay, "PREFIX_OVERLAY_READBACK")
    return {"source_sha256": NATIVE_SOURCE_SHA256, "overlay_sha256": sha(overlay),
            "overlay_bytes": str(len(overlay))}


def binding(run_id: str) -> dict[str, Any]:
    """Return the unchanged full-mode input contract for the diagnostic prefix."""
    _need(type(run_id) is str and _ID.fullmatch(run_id) is not None, "PREFIX_RUN_ID")
    return {"schema_id": "hh-studio.native-cycle-benchmark-run", "schema_version": "1.2.0",
            "run_id": run_id, "mode": "full", "source_closure_sha256": SOURCE_CLOSURE_SHA256,
            "profile_sha256": PROFILE_SHA256, "batch_barrier": "host_ack_v1",
            "batch_start": "host_permit_v1"}


def plan(run_id: str) -> dict[str, Any]:
    """Build a reviewable launch plan; constructing it has no side effects."""
    sources = verify_source53()
    _need(sha(_read_regular(STUDIO / "tests/replay/benchmark_native.gd")) == NATIVE_SOURCE_SHA256,
          "PREFIX_NATIVE_SOURCE_DRIFT")
    return {"schema_id": "hh-studio.gt06-s103-prefix-plan", "schema_version": "1.0.0",
            "run_id": run_id, "source_checkpoint": SOURCE_CHECKPOINT,
            "source_closure_sha256": SOURCE_CLOSURE_SHA256, "source_file_count": len(sources),
            "profile_sha256": PROFILE_SHA256, "native_source_sha256": NATIVE_SOURCE_SHA256,
            "preflight": {"http_commands": PREFLIGHT_HTTP_COMMANDS,
                          "native_cycles": PREFLIGHT_NATIVE_CYCLES, "exactly_one": True},
            "prefix": {"batch_indices": list(PREFIX_BATCH_INDICES),
                        "batch_count": MAX_PREFIX_BATCHES, "cycles_per_batch": FULL_PROFILE_CYCLES,
                        "outer_wall_seconds": OUTER_WALL_SECONDS,
                        "stop_at_status_gap_ms": STATUS_GAP_LIMIT_MS},
            "formal_acceptance": FORMAL_ACCEPTANCE,
            "eligible_for_dataset": False,
            "binding": binding(run_id),
            "cleanup": {"fresh_run_root": True, "preserve_failure": True,
                         "require_target_and_helper_exit": True,
                         "no_pid_reuse_or_blind_kill": True}}


def main(argv: list[str] | None = None) -> int:
    """Static-only command: print the frozen plan and never launch Godot."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="gt06-s103-prefix-static")
    parser.add_argument("--check", action="store_true", help="verify source53 and overlay deterministically")
    args = parser.parse_args(argv)
    value = plan(args.run_id)
    if args.check:
        overlay = generated_native_overlay()
        _need(overlay.endswith(_load_native_probe()._SUFFIX), "PREFIX_OVERLAY_SUFFIX")
        value["overlay_sha256"] = sha(overlay)
        value["overlay_bytes"] = len(overlay)
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
