"""Read-only postcheck for the retained GT07 installed binding refresh."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


BASE = Path(__file__).resolve().parent
ROOT = next(parent for parent in BASE.parents if (parent / "studio").is_dir())
sys.path.insert(0, str(ROOT))
from studio.host.replay import execution_installed as installed  # noqa: E402
from studio.host.replay import native_runner as native  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify() -> dict:
    receipt = json.loads((BASE / "refresh-receipt.json").read_bytes())
    for generation in ("old", "new"):
        for name, digest in receipt[f"{generation}_metadata_sha256"].items():
            assert sha((BASE / generation / Path(name).name).read_bytes()) == digest
    old = json.loads((BASE / "old/execution-source.json").read_bytes())
    new = json.loads((BASE / "new/execution-source.json").read_bytes())
    assert old["schema"] == new["schema"]
    assert old["accepted_gt05_manifest_sha256"] == new["accepted_gt05_manifest_sha256"]
    old_files, new_files = old["source_files"], new["source_files"]
    delta = [name for name in sorted(set(old_files) | set(new_files))
             if old_files.get(name) != new_files.get(name)]
    assert delta == receipt["source_delta"]
    actual_metadata = {
        name: sha((native.STUDIO / name).read_bytes())
        for name in installed.METADATA_PATHS
    }
    assert actual_metadata == receipt["new_metadata_sha256"]
    _inputs, accepted = native.accepted_inputs()
    verified = native.sources(accepted)
    assert verified == dict(sorted({**new_files, **actual_metadata}.items()))
    assert len(new_files) == 233 and len(verified) == 235
    return {
        "authority": 0,
        "formal_acceptance": False,
        "engine_runs": 0,
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "operation": "READ_ONLY_GT07_BINDING_POSTCHECK",
        "source_count": len(new_files),
        "execution_count": len(verified),
        "source_closure_sha256": native.closure(new_files),
        "execution_closure_sha256": native.closure(verified),
        "metadata": installed.selection_identity(native.STUDIO),
        "delta": delta,
    }


if __name__ == "__main__":
    result = verify()
    output = BASE / "postcheck-01.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))
