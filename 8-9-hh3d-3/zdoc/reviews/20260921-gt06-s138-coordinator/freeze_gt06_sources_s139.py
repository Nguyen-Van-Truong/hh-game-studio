"""Read-only GT06 source/input projection freeze; no engine or test launch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / "studio"
OUT = BASE / "source-freeze-s139.json"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def closure(files: dict[str, str]) -> str:
    return digest("".join(name + "\0" + files[name] + "\n"
                          for name in sorted(files)).encode())


def load_benchmark_projection() -> dict[str, str]:
    # Use the locked 53-name benchmark projection from the last diagnostic;
    # re-hash current bytes instead of inheriting its old digest.
    path = ROOT / "zdoc/reviews/20260920-gt06-s131-rss-failure/raw/campaign.json"
    names = json.loads(path.read_text(encoding="utf-8"))["source_files"]
    result = {}
    for name in sorted(names):
        file = STUDIO / name
        result[name] = digest(file.read_bytes())
    return result


def load_benchmark_expected() -> dict[str, str]:
    path = ROOT / "zdoc/reviews/20260920-gt06-s131-rss-failure/raw/campaign.json"
    return dict(sorted(json.loads(path.read_text(encoding="utf-8"))["source_files"].items()))


def load_installed_projection() -> dict[str, str]:
    code = ("import json,sys;sys.path.insert(0,sys.argv[1]);"
            "from studio.host.replay import native_runner;"
            "inputs,manifest=native_runner.accepted_inputs();"
            "print(json.dumps(native_runner.sources(manifest),sort_keys=True))")
    repo = str(ROOT)
    completed = subprocess.run([sys.executable, "-B", "-c", code, repo],
                               cwd=ROOT, check=True, capture_output=True, text=True)
    return dict(sorted(json.loads(completed.stdout).items()))


def input_projection() -> dict[str, object]:
    manifest_path = STUDIO.parent / "zdoc/reviews/20260917-gt05-s63-audit/manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    names = ("fixture.glb", "manifest.json", "producer-report.json")
    files = {}
    for name in names:
        relative = ".local/reviews/gt05-validation-s62-01/" + name
        payload = (STUDIO / relative).read_bytes()
        files[relative] = {
            "sha256": digest(payload),
            "manifest_sha256": manifest["raw_files"].get(relative),
            "size": len(payload),
        }
    return {
        "accepted_manifest_sha256": digest(raw),
        "files": files,
        "all_manifest_bindings_match": all(
            row["sha256"] == row["manifest_sha256"] for row in files.values()
        ),
    }


def main() -> int:
    benchmark = load_benchmark_projection()
    benchmark_expected = load_benchmark_expected()
    installed = load_installed_projection()
    overlap = sorted(set(benchmark) & set(installed))
    equal_overlap = [name for name in overlap if benchmark[name] == installed[name]]
    union = dict(sorted({**installed, **benchmark}.items()))
    profile = STUDIO / "host/replay/profile.json"
    toolchain = STUDIO / "toolchain.lock.json"
    result = {
        "schema": "HH-GT06-S139-SOURCE-FREEZE-1",
        "authority": 0,
        "formal_acceptance": False,
        "source_unchanged_during_freeze": True,
        "benchmark": {"count": len(benchmark), "closure_sha256": closure(benchmark),
                      "historical_closure_sha256": closure(benchmark_expected),
                      "current_matches_historical": benchmark == benchmark_expected,
                      "source_files": benchmark},
        "installed_execution": {"count": len(installed), "closure_sha256": closure(installed),
                                 "source_files": installed},
        "union": {"count": len(union), "closure_sha256": closure(union),
                  "overlap_count": len(overlap), "equal_overlap_count": len(equal_overlap),
                  "overlap_all_equal": len(overlap) == len(equal_overlap)},
        "profile": {"path": profile.relative_to(ROOT).as_posix(),
                    "sha256": digest(profile.read_bytes())},
        "toolchain": {"path": toolchain.relative_to(ROOT).as_posix(),
                      "sha256": digest(toolchain.read_bytes())},
        "gt05_inputs": input_projection(),
        "managed_s138": {
            "repair_capture_sha256": digest(
                (STUDIO / ".local/reviews/gt06-s138-managed-repair-01/capture.json").read_bytes()
            ),
            "replay_summary_sha256": digest(
                (STUDIO / ".local/reviews/gt06-s138-managed-replay-01/repair-replay.json").read_bytes()
            ),
            "formal_acceptance": False,
        },
        "next_gate": "RSS_EFFECT_AND_FORMAL_DATASET_PREP",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(json.dumps({"written": OUT.as_posix(), "benchmark_count": len(benchmark),
                      "installed_count": len(installed), "union_count": len(union),
                      "overlap_equal": len(overlap) == len(equal_overlap),
                      "formal_acceptance": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
