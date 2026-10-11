"""Reject hostile copies of actual Linux raw evidence, without engine reruns."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.package.release_contract import digest_file, need
from studio.tests.conformance.gt10pc_linux_verify import verify_linux


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def rebind(root):
    native = read(root / "native/linux.json")
    for name in native["evidence"]:
        native["evidence"][name] = digest_file(root / "native" / name)
    write(root / "native/linux.json", native)
    doc = read(root / "producer.json")
    for name in doc["evidence"]:
        doc["evidence"][name] = digest_file(root / name)
    write(root / "producer.json", doc)


def run(source, *, artifact, upgrade_artifact, trust, trust_sha256):
    args = dict(artifact=artifact, upgrade_artifact=upgrade_artifact,
                trust=trust, trust_sha256=trust_sha256)
    baseline = verify_linux(source, **args)
    doc = read(source / "producer.json")
    results = []
    with tempfile.TemporaryDirectory(prefix="hh-linux-evidence-") as temporary:
        for attack in ("raw-hash", "host-exit", "network", "docker-error", "missing-install",
                       "profile-leak", "partial-lifecycle", "consumer-asset", "wrong-target"):
            root = Path(temporary) / attack
            for name in ("producer.json", *doc["evidence"]):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, target)
            verify_linux(root, **args)
            if attack == "raw-hash":
                with (root / "host/run-stdout.txt").open("ab") as stream:
                    stream.write(b"unrecorded bytes")
            elif attack == "host-exit":
                path = root / "native/consumer/gt09-arena/native/install/godot-host.json"
                value = read(path); value["exit_code"] = 71; write(path, value)
                rebind(root)
            elif attack in ("network", "docker-error"):
                label = "inspect-exited"
                path = root / ("host/" + label + "-stdout.txt")
                value = read(path)
                if attack == "network":
                    value[0]["HostConfig"]["NetworkMode"] = "bridge"
                else:
                    value[0]["State"]["Error"] = "unexplained failure"
                write(path, value)
                producer = read(root / "producer.json")
                producer["inspections"][label] = value[0]
                write(root / "producer.json", producer)
                rebind(root)
            elif attack == "missing-install":
                name = "consumer/gt09-arena/native/install/godot-host.json"
                (root / "native" / name).unlink()
                native = read(root / "native/linux.json"); del native["evidence"][name]
                write(root / "native/linux.json", native)
                producer = read(root / "producer.json"); del producer["evidence"]["native/" + name]
                write(root / "producer.json", producer)
                rebind(root)
            elif attack == "profile-leak":
                path = root / "native/consumer/gt09-room/native/rollback/receipt.json"
                value = read(path); value["profile"]["other"] = value["profile"]["own"]
                write(path, value); rebind(root)
            elif attack == "partial-lifecycle":
                path = root / "native/consumer/gt09-room/native/reinstall/godot-stdout.txt"
                path.write_text("\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                                          if "LIFECYCLE_SUMMARY" not in line), encoding="utf-8")
                rebind(root)
            elif attack == "consumer-asset":
                path = root / "native/consumer/gt09-arena/project-after-uninstall.json"
                value = read(path); del value["assets/avatar.glb"]; write(path, value); rebind(root)
            try:
                if attack == "wrong-target":
                    from studio.package.trust import load_trust
                    from studio.package.release_contract import verify_package
                    verify_package(artifact, trusted_keys=load_trust(trust, expected_sha256=trust_sha256),
                                   target="Windows")
                else:
                    verify_linux(root, **args)
            except (ValueError, OSError) as exc:
                results.append({"attack": attack, "rejected": True, "reason": str(exc)})
            else:
                raise ValueError("GT10PC_LINUX_EVIDENCE_ATTACK_ACCEPTED:" + attack)
    need(len(results) == 9, "GT10PC_LINUX_ATTACK_SET")
    return {"status": "HOST_ATTACK_CHECKS_PASS", "authority": 0, "acceptance": False,
            "baseline": baseline, "checks": results}


def main():
    parser = argparse.ArgumentParser()
    for name in ("evidence", "artifact", "upgrade-artifact", "trust"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--trust-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.evidence, artifact=args.artifact, upgrade_artifact=args.upgrade_artifact,
                         trust=args.trust, trust_sha256=args.trust_sha256), sort_keys=True))


if __name__ == "__main__":
    main()
