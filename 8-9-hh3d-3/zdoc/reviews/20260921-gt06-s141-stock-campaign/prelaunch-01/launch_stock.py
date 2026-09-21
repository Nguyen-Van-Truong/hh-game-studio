"""One-use frozen entry to the unchanged GT06 campaign, passively supervised.

No instrumentation or method replacement. Stock run_campaign owns every child
and stops on its first exception. Successful process exit is not acceptance.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import sys
import traceback

BASE = Path(__file__).resolve().parent
HH3D = BASE.parents[2]
CAMPAIGN_ID = "gt06-s141-formal-01"
CLOSURE = "763191109cd7c7f63de499680291c6b99d77a501dad869078e6d77384ecb20b4"
PROFILE = "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def check():
    freeze = json.loads((BASE/"freeze.json").read_bytes())
    for name, digest in freeze["files"].items():
        if sha(HH3D/name) != digest:
            raise RuntimeError("S141_FROZEN_SOURCE_OR_INPUT_CHANGED")
    for name, digest in freeze["binaries"].items():
        if sha(Path(name)) != digest:
            raise RuntimeError("S141_BINARY_CHANGED")
    sys.path.insert(0, str(HH3D))
    from studio.tests.replay import run_benchmark_campaign as campaign
    campaign.load_fixture()
    if campaign.closure(campaign.source_files()) != CLOSURE or campaign.profile.PROFILE_SHA256 != PROFILE:
        raise RuntimeError("S141_CAMPAIGN_PIN_CHANGED")
    if campaign.workstation_profile() != freeze["workstation"]:
        raise RuntimeError("S141_WORKSTATION_CHANGED")
    return campaign


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    campaign = check()
    root = HH3D/"studio/.local/reviews"/CAMPAIGN_ID
    if not args.run:
        print(json.dumps({"checked": True, "launched": False, "campaign": CAMPAIGN_ID}))
        return 0
    if root.exists():
        raise RuntimeError("S141_FRESH_CAMPAIGN_REQUIRED")
    # A repeated scheduler start cannot resume a failed pair or erase Stop.
    write(BASE/"dispatch-once.json", {"campaign_id": CAMPAIGN_ID,
          "created_utc": datetime.now(timezone.utc).isoformat(), "pid": os.getpid()})
    code = 1
    error = None
    try:
        code = campaign.run_campaign(CAMPAIGN_ID, root)
        check()
        return code
    except BaseException as failure:
        error = {"type": type(failure).__name__, "code": getattr(failure, "code", None)}
        traceback.print_exc()
        raise
    finally:
        write(BASE/"launcher-return.json", {"campaign_id": CAMPAIGN_ID,
              "returned_code": code, "error": error, "actual_exit_not_yet_observed": True,
              "formal_acceptance": False, "ended_utc": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    raise SystemExit(main())
