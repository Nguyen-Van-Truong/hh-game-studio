"""Host-only adversarial checks on disposable copies of real native evidence.

The original run is read-only. These checks do not mint native acceptance.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.conformance import run_gt10pc_matrix as verifier
from studio.package.release_contract import digest_file, need


def write(path, document):
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")


def rebind(root):
    p = json.loads((root / "producer.json").read_bytes())
    for name in p["evidence"]:
        p["evidence"][name] = digest_file(root / name)
    for row in p["fixtures"]:
        for name in row["ledger_sha256"]:
            row["ledger_sha256"][name] = p["evidence"]["consumer/" + row["fixture"] + "/" + name]
    write(root / "producer.json", p)
    m = json.loads((root / "matrix.json").read_bytes())
    m["producer_sha256"] = digest_file(root / "producer.json")
    write(root / "matrix.json", m)


def clone(source, destination):
    producer = json.loads((source / "producer.json").read_bytes())
    for name in ("producer.json", "matrix.json", "release.hhpkg", "upgrade.hhpkg", *producer["evidence"]):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    # Relocate the absolute receipt location, then rebind the transport hashes.
    # The signed artifact is unchanged; no native receipt contents are invented.
    for name in producer["evidence"]:
        if name.startswith("godot/") and name.endswith("/receipt.json"):
            target = destination / name
            doc = json.loads(target.read_bytes())
            doc["studio"] = str(destination / Path(doc["studio"]).relative_to(source))
            write(target, doc)
    rebind(destination)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--trust", type=Path, required=True)
    parser.add_argument("--trust-sha256", required=True)
    args = parser.parse_args()
    source = args.evidence.absolute()
    verify = lambda p: verifier.verify_only(p, trust=args.trust, trust_sha256=args.trust_sha256)
    verify(source)
    outcomes = []
    with tempfile.TemporaryDirectory(prefix="hh-gt10pc-attacks-") as td:
        for attack in ("raw-hash", "host-exit", "partial-lifecycle", "godot-pin", "project-asset", "phase-release", "artifact", "trust"):
            root = Path(td) / attack
            clone(source, root)
            verify(root)  # Relocation itself must be valid before each attack.
            if attack == "raw-hash":
                with (root / "godot/gt09-arena/godot-stdout.txt").open("ab") as stream:
                    stream.write(b"unrecorded change")
            elif attack == "artifact":
                path = root / "release.hhpkg"
                path.write_bytes(path.read_bytes()[:-20])
            elif attack == "trust":
                pass
            else:
                if attack == "host-exit":
                    path = root / "godot/gt09-arena/godot-host.json"
                    doc = json.loads(path.read_bytes()); doc["exit_code"] = 1
                elif attack == "godot-pin":
                    path = root / "godot/gt09-arena/receipt.json"
                    doc = json.loads(path.read_bytes()); doc["godot_sha256"] = "0" * 64
                elif attack == "project-asset":
                    path = root / "consumer/gt09-arena/project-after-uninstall.json"
                    doc = json.loads(path.read_bytes()); del doc["assets/avatar.glb"]
                elif attack == "phase-release":
                    path = root / "consumer/gt09-arena/native-phases.json"
                    doc = json.loads(path.read_bytes()); doc["phases"][1]["active"] = doc["phases"][0]["active"]
                else:
                    path = root / "godot/gt09-arena/godot-stdout.txt"
                    lines = path.read_text(encoding="utf-8").splitlines()
                    path.write_text("\n".join(line for line in lines if "LIFECYCLE_SUMMARY" not in line), encoding="utf-8")
                    doc = None
                if doc is not None: write(path, doc)
                rebind(root)  # A consistent hash ledger must not hide semantic tampering.
            try:
                if attack == "trust":
                    verifier.verify_only(root, trust=args.trust, trust_sha256="0" * 64)
                else:
                    verify(root)
            except (ValueError, OSError) as exc:
                outcomes.append({"attack": attack, "rejected": True, "reason": str(exc)})
            else:
                raise RuntimeError("evidence attack accepted: " + attack)
    need(len(outcomes) == 8, "incomplete attack checks")
    print(json.dumps({"status": "HOST_ATTACK_CHECKS_PASS", "authority": 0,
                      "acceptance": False, "checks": outcomes}, sort_keys=True))


if __name__ == "__main__":
    main()
