"""Shared rehearsal/final raw verification. No native launch or evidence write."""
from contextlib import contextmanager
from pathlib import Path

from studio.package.release_contract import verify_package, need, digest_file, _source_files, _payload_digest
from studio.package.trust import load_trust


@contextmanager
def _row(errors: dict, name: str):
    """Record a row failure and keep checking the other rows; never a PASS."""
    try:
        yield
    except (ValueError, OSError, KeyError, TypeError) as exc:
        errors[name] = type(exc).__name__ + ": " + str(exc)


def _verify_p11_10x35(root: Path, row: dict, *, package: dict, profile, campaign) -> dict:
    """Reassemble five immutable 2x35 campaigns; never trust pooled counters."""
    from studio.tests.conformance import run_gt10pc_matrix as matrix
    campaigns = row.get("campaigns")
    need(row.get("coverage") == "formal-10x35" and row.get("full_benchmark") is True
         and row.get("campaign_count") == 5 and row.get("pair_count") == 10
         and row.get("total_batches") == 350 and row.get("measured_batches") == 300
         and row.get("measured_commands") == 300000 and row.get("measured_cycles") == 30000
         and isinstance(campaigns, list) and len(campaigns) == 5, "GT10PC_P11_10X35_SUMMARY")
    identities = set()
    checked = []
    for item in campaigns:
        need(isinstance(item, dict), "GT10PC_P11_CAMPAIGN_ROW")
        campaign_id, campaign_root = item.get("campaign_id"), Path(item.get("root", "")).resolve()
        review_root = (matrix.ROOT / ".local" / "reviews").resolve()
        need(isinstance(campaign_id, str) and campaign_root.parent == review_root
             and campaign_root.name == campaign_id and review_root in campaign_root.parents,
             "GT10PC_P11_CAMPAIGN_SCOPE")
        receipt = item.get("receipt")
        receipt_dir = (root / "campaign-receipts").resolve()
        need(matrix._read(receipt_dir / (str(campaign_id) + "-receipt.json")) == receipt,
             "GT10PC_P11_CAMPAIGN_RECEIPT_FILE")
        need(isinstance(receipt, dict) and receipt.get("schema") == "hh-gt10pc-p11-campaign-receipt-1"
             and receipt.get("campaign_id") == campaign_id and receipt.get("exit_code") == 0
             and receipt.get("timed_out") is False and receipt.get("pid", 0) > 0,
             "GT10PC_P11_CAMPAIGN_RECEIPT")
        for key in ("stdout", "stderr"):
            stream = Path(receipt[key]).resolve()
            need(stream.parent == receipt_dir and stream.is_file() and digest_file(stream) == receipt[key + "_sha256"], "GT10PC_P11_CAMPAIGN_STREAM")
        capture_path = campaign_root / "campaign-capture.json"
        dataset_path, summary_path = campaign_root / "dataset.json", campaign_root / "summary.json"
        capture, frozen = matrix._read_large_json(capture_path), matrix._read_large_json(campaign_root / "campaign.json")
        dataset, summary = matrix._read_large_json(dataset_path), matrix._read_large_json(summary_path)
        need(item.get("campaign_sha256") == digest_file(capture_path)
             and item.get("dataset_sha256") == digest_file(dataset_path)
             and item.get("summary_sha256") == digest_file(summary_path)
             and capture.get("campaign_id") == campaign_id and capture.get("completed") is True
             and capture.get("formal_acceptance") is False and capture.get("profile_sha256") == profile.PROFILE_SHA256
             and frozen.get("campaign_id") == campaign_id and frozen.get("run_count") == 2
             and frozen.get("batches_per_run") == 35 and frozen.get("formal_acceptance") is False,
             "GT10PC_P11_CAMPAIGN_BINDING")
        need(summary == profile.summarize_dataset(profile.validate_dataset(dataset))
             and summary.get("status") == "PASS" and summary.get("measured_batches") == 60
             and summary.get("measured_commands") == 60000 and summary.get("measured_cycles") == 6000,
             "GT10PC_P11_CAMPAIGN_DATASET")
        source_files = frozen.get("source_files")
        need(isinstance(source_files, dict) and source_files, "GT10PC_P11_CAMPAIGN_SOURCES")
        for relative, digest in source_files.items():
            member = "payload/studio/" + relative
            need(member in package["members"] and digest_file(campaign_root / "source/studio" / relative) == digest
                 and package["manifest"]["files"].get(member, {}).get("sha256") == digest,
                 "GT10PC_P11_RELEASE_BYTE_BINDING")
        need(item.get("release_binding", {}).get("release_manifest_sha256") == package["manifest_sha256"],
             "GT10PC_P11_RELEASE_MANIFEST")
        runs = capture.get("runs")
        need(isinstance(runs, list) and len(runs) == 2, "GT10PC_P11_RUN_COUNT")
        run_rows = []
        for run_ref in runs:
            ref = run_ref.get("capture")
            need(isinstance(ref, dict) and isinstance(ref.get("file"), str), "GT10PC_P11_RUN_REFERENCE")
            run_capture = campaign_root / ref["file"]
            need(run_capture.is_file() and digest_file(run_capture) == ref.get("sha256"), "GT10PC_P11_RUN_CAPTURE_HASH")
            captured = matrix._read_large_json(run_capture)
            attempt = int(run_capture.parent.name.rsplit("-attempt-", 1)[1])
            verified = campaign.verify_run_capture(run_capture.parent, captured, frozen["source_closure_sha256"],
                campaign_id=campaign_id, index=run_ref["index"], attempt=attempt,
                campaign_sha256=capture["campaign_sha256"])
            binding = matrix._read_large_json(run_capture.parent / "role-process-binding.json")
            need(set(binding.get("roles", {})) == {"host", "editor"}, "GT10PC_P11_ROLE_BINDING")
            for role in ("host", "editor"):
                ident = binding["roles"][role]
                key = (role, ident.get("pid"), ident.get("process_start"))
                need(key not in identities and key[1] > 0 and isinstance(key[2], str), "GT10PC_P11_DUPLICATE_IDENTITY")
                identities.add(key)
            run_rows.append({"index": run_ref["index"], "run_id": captured["run_id"],
                             "host_pid": verified["processes"]["host"]["pid"],
                             "editor_pid": verified["processes"]["editor"]["pid"]})
        checked.append({"campaign_id": campaign_id, "runs": run_rows})
    need(len(identities) == 20, "GT10PC_P11_IDENTITY_COUNT")
    need(row.get("matrix_source_closure_sha256") == package["manifest"]["source_closure_sha256"],
         "GT10PC_P11_MATRIX_SOURCE")
    return {"coverage": "formal-10x35", "campaigns": checked, "pair_count": 10,
            "measured_batches": 300, "measured_commands": 300000, "measured_cycles": 30000}


def verify_matrix(root: Path, *, trust: Path, trust_sha256: str, mode: str) -> dict:
    from studio.tests.conformance import run_gt10pc_matrix as matrix
    doc = matrix._read(root / "matrix.json")
    need(mode in ("REHEARSAL", "FINAL") and doc.get("schema") == matrix.SCHEMA
         and doc.get("mode") == mode and doc.get("authority") == 0
         and doc.get("acceptance") is False and doc.get("status") == mode + "_PASS", "GT10PC_VERIFY_SCHEMA")
    requested, rows = doc.get("rows_requested"), doc.get("rows")
    need(isinstance(requested, list) and requested and len(requested) == len(set(requested))
         and set(requested) <= set(matrix.FINAL_ROWS) and isinstance(rows, dict)
         and set(rows) == set(requested), "GT10PC_VERIFY_ROWS")
    if mode == "FINAL":
        need(requested == list(matrix.FINAL_ROWS), "GT10PC_VERIFY_FINAL_ROWS")
    for name in requested:
        need(isinstance(rows[name], dict) and rows[name].get("status") == mode + "_PASS", "GT10PC_VERIFY_STATUS:" + name)
    result = verify_raw_rows(root, doc, trust=trust, trust_sha256=trust_sha256)
    observed = _payload_digest(_source_files(matrix.ROOT))
    if doc.get("source_closure_sha256") != observed:
        # Validators still ran on the raw; a drifted tree can never print a PASS.
        result["findings"] = [{"code": "SOURCE_DRIFT", "recorded": doc.get("source_closure_sha256"),
                               "observed": observed}]
        result["status"] = "DIAGNOSTIC_SOURCE_DRIFT"
    return result


def verify_raw_rows(root: Path, doc: dict, *, trust: Path, trust_sha256: str) -> dict:
    """Also callable on historical raw for diagnostic tests after source edits.

    This function deliberately issues no matrix PASS. The public verifier
    above additionally requires the frozen source and exact mode/row set.
    """
    from studio.tests.conformance import run_gt10pc_matrix as matrix
    rows, artifacts = doc["rows"], doc["artifacts"]
    need(isinstance(artifacts, dict) and set(artifacts) == {"Windows", "Linux-headless"}, "GT10PC_VERIFY_ARTIFACTS")
    keys = load_trust(trust, expected_sha256=trust_sha256)
    packages = {}
    for target in ("Windows", "Linux-headless"):
        need(set(artifacts[target]) == {"0.1.0", "0.1.1"}, "GT10PC_VERIFY_VERSIONS")
        for version in ("0.1.0", "0.1.1"):
            item = artifacts[target][version]
            archive = Path(item.get("path", ""))
            need(root.resolve() in archive.resolve().parents, "GT10PC_VERIFY_ARCHIVE_SCOPE")
            package = verify_package(archive, trusted_keys=keys, target=target, expected_version=version)
            need(package["archive_sha256"] == item.get("archive_sha256")
                 and package["manifest_sha256"] == item.get("manifest_sha256")
                 and package["manifest"]["source_closure_sha256"] == item.get("source_closure_sha256")
                 == doc.get("source_closure_sha256"), "GT10PC_VERIFY_ARCHIVE_BINDING")
            packages[target, version] = package
    selected = packages["Windows", "0.1.0"]
    checked, errors = {}, {}
    if "P1" in rows:
        with _row(errors, "P1"):
            from studio.tests.conformance.gt10pc_p1_scan import scan_archive
            need(rows["P1"].get("targets") == ["Windows", "Linux-headless"], "GT10PC_VERIFY_P1")
            scans = {target + "/" + version: scan_archive(Path(artifacts[target][version]["path"]))
                     for target in ("Windows", "Linux-headless") for version in ("0.1.0", "0.1.1")}
            need(rows["P1"].get("scans") == scans, "GT10PC_VERIFY_P1_SCAN")
            checked["P1"] = {"archives": 4, "scans": scans}
    if "P2" in rows:
        with _row(errors, "P2"):
            checks = []
            for target in ("Windows", "Linux-headless"):
                original = Path(artifacts[target]["0.1.0"]["path"]).read_bytes()
                for attack in ("truncate", "tamper", "wrong-version", "wrong-target"):
                    candidate = root / "p2-attacks" / target / (attack + ".hhpkg")
                    expected = (original[:-19] if attack == "truncate" else
                        original[:len(original)//2] + bytes([original[len(original)//2] ^ 1]) + original[len(original)//2+1:]
                        if attack == "tamper" else original)
                    need(candidate.read_bytes() == expected, "GT10PC_VERIFY_P2_ATTACK_BYTES")
                    try:
                        verify_package(candidate, trusted_keys=keys,
                            target=("Linux-headless" if target == "Windows" else "Windows") if attack == "wrong-target" else target,
                            expected_version="0.1.1" if attack == "wrong-version" else "0.1.0")
                    except ValueError as exc:
                        checks.append({"target": target, "attack": attack, "rejected": True, "reason": str(exc)})
                    else:
                        raise ValueError("GT10PC_VERIFY_P2_ATTACK_ACCEPTED")
            checks.append(matrix._verify_p2_native(root, artifacts, trust=trust, trust_sha256=trust_sha256))
            need(checks == rows["P2"].get("archive_and_native_attacks"), "GT10PC_VERIFY_P2_ROWS")
            checked["P2"] = {"host_attacks": 8, "native_attacks": 4}
    if any(name in rows for name in ("P3", "P4", "P5", "P6")):
        with _row(errors, "P3-P6"):
            from studio.tests.conformance.gt10pc_linux_verify import verify_linux
            process = matrix._read(root / "children/windows-producer-receipt.json")
            matrix._process(root / "children", "windows-producer", process, check_log=False)
            win = matrix._verify_native_producer(root / "windows", trust=trust, trust_sha256=trust_sha256)
            for version, name in (("0.1.0", "release.hhpkg"), ("0.1.1", "upgrade.hhpkg")):
                bound = verify_package(root / "windows" / name, trusted_keys=keys, target="Windows", expected_version=version)
                need(bound["manifest_sha256"] == packages["Windows", version]["manifest_sha256"], "GT10PC_VERIFY_WINDOWS_RELEASE")
            linux = verify_linux(root / "linux",
                artifact=Path(artifacts["Linux-headless"]["0.1.0"]["path"]),
                upgrade_artifact=Path(artifacts["Linux-headless"]["0.1.1"]["path"]), trust=trust, trust_sha256=trust_sha256)
            for name in ("P3", "P4", "P5", "P6"):
                if name in rows:
                    checked[name] = {"windows": win, "linux": linux}
    if "P7" in rows:
        with _row(errors, "P7"):
            from studio.tests.conformance.gt10pc_p7_verify import verify_p7
            checked["P7"] = []
            producers = rows["P7"].get("producers")
            need(isinstance(producers, list) and len(producers) == 3 and rows["P7"].get("cases") == 8, "GT10PC_VERIFY_P7_ROWS")
            for item, (suffix, group) in zip(producers, (("a", "first"), ("b", "second"), ("c", "third"))):
                label = "p7-native-" + suffix
                need(item.get("producer") == label and item.get("group") == group, "GT10PC_VERIFY_P7_GROUP")
                receipt = matrix._read(root / "children" / (label + "-receipt.json"))
                need(receipt == item.get("child"), "GT10PC_VERIFY_P7_CHILD")
                matrix._process(root / "children", label, receipt)
                host = matrix._read(root / "children" / (label + "-host.json"))
                checked["P7"].append(verify_p7(root / label, trust=trust, trust_sha256=trust_sha256,
                                               group=group, release=selected, group_host=host))
    if "P8" in rows:
        with _row(errors, "P8"):
            from studio.tests.conformance.gt10pc_p8_checks import verify_p8
            checked["P8"] = verify_p8(root / "p8-host", artifact=Path(artifacts["Windows"]["0.1.0"]["path"]),
                                     trust=trust, trust_sha256=trust_sha256)
            need(rows["P8"] == {**checked["P8"], "status": doc["mode"] + "_PASS", "evidence_kind": "host"}, "GT10PC_VERIFY_P8_ROW")
    if "P9" in rows:
        with _row(errors, "P9"):
            from studio.tests.conformance.gt10pc_p9_consumer import verify_consumer
            receipt = matrix._read(root / "children/p9-consumer-receipt.json")
            matrix._process(root / "children", "p9-consumer", receipt, check_log=False)
            checked["P9"] = verify_consumer(root / "p9-consumer", Path(artifacts["Windows"]["0.1.0"]["path"]),
                                           trust=trust, trust_sha256=trust_sha256)
            need(rows["P9"] == {**checked["P9"], "status": doc["mode"] + "_PASS", "child": receipt},
                 "GT10PC_VERIFY_P9_ROW")
    if "P10" in rows:
        with _row(errors, "P10"):
            from studio.tests.conformance.gt10pc_p10 import verify as verify_p10
            producers = rows["P10"].get("producers")
            need(isinstance(producers, list) and len(producers) == 3, "GT10PC_VERIFY_P10_COUNT")
            checked["P10"] = []
            for item, phase in zip(producers, ("gt08a", "catalog", "linux")):
                label = "p10-installed-" + phase
                need(item.get("phase") == phase and Path(item.get("path", "")).resolve() == (root / ("p10-" + phase)).resolve(),
                     "GT10PC_VERIFY_P10_PATH")
                receipt = matrix._read(root / "children" / (label + "-receipt.json"))
                need(receipt == item.get("child"), "GT10PC_VERIFY_P10_CHILD")
                matrix._process(root / "children", label, receipt, check_log=False)
                result = verify_p10(root / ("p10-" + phase))
                release = packages["Linux-headless", "0.1.0"] if phase == "linux" else selected
                need(result.get("manifest_sha256") == release["manifest_sha256"] == item.get("manifest_sha256")
                     and result.get("source_closure_sha256") == doc["source_closure_sha256"]
                     == item.get("source_closure_sha256"), "GT10PC_VERIFY_P10_RELEASE")
                if phase == "linux":
                    # The closure the container hashed must be the signed package's sample-game bytes.
                    prefix, sample = "payload/studio/fixtures/sample-game/", root / "p10-linux" / "sample-game"
                    expected = {name[len(prefix):]: row["sha256"] for name, row in release["manifest"]["files"].items()
                                if name.startswith(prefix)}
                    observed = {path.relative_to(sample).as_posix(): digest_file(path)
                                for path in sample.rglob("*") if path.is_file()}
                    need(expected and observed == expected, "GT10PC_VERIFY_P10_SAMPLE_GAME")
                checked["P10"].append({"phase": phase, "manifest_sha256": result["manifest_sha256"]})
    if "P11" in rows:
        with _row(errors, "P11"):
            if doc["mode"] == "REHEARSAL":
                child = rows["P11"].get("child")
                need(matrix._read(root / "p11-short-child/p11-short-receipt.json") == child, "GT10PC_VERIFY_P11_CHILD")
                matrix._process(root / "p11-short-child", "p11-short", child, check_log=False)
                checked["P11"] = matrix._verify_p11_short_row(root, rows["P11"])
            else:
                from studio.tests.replay import benchmark_profile as profile
                from studio.tests.replay import run_benchmark_campaign as campaign
                checked["P11"] = _verify_p11_10x35(root, rows["P11"],
                    package=selected, profile=profile, campaign=campaign)
    missing = sorted(set(rows) - set(checked) - {"P3", "P4", "P5", "P6", "P12"} - set(errors))
    need(not missing, "GT10PC_VERIFY_UNCHECKED_ROWS:" + ",".join(missing))
    return {"schema": matrix.SCHEMA, "authority": 0, "acceptance": False, "mode": doc["mode"],
            "status": "DIAGNOSTIC_FAIL" if errors else "RAW_VERIFIED", "rows": checked, "errors": errors}
