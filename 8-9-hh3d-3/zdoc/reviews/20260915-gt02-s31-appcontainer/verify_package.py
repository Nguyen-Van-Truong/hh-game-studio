"""Read-only S31 verifier. Never regenerates a hash ledger or launches probes."""
import argparse
import hashlib
import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
PRODUCT = BASE.parents[2]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def redact_raw(raw):
    broker = re.search(r"O:(S-1-5-21-\d+-\d+-\d+-\d+)", raw["effective_sddl"]["scratch"]).group(1)
    system_root = str(Path(raw["control"]["application_name"]).parent.parent)
    replacements = [(raw["fixture_root"], "<OWNED_TEMP>"), (raw["profile_path"], "<OWNED_PROFILE_PATH>"),
                    (broker, "<BROKER_SID>"), (raw["package_sid"], "<APPCONTAINER_SID>"),
                    (raw["profile_name"], "<OWNED_PROFILE_NAME>"),
                    (str(Path(raw["profile_path"]).parents[3]), "<USER_PROFILE>"), (system_root, "<SYSTEM_ROOT>")]
    def walk(value):
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str):
            for old, new in replacements:
                value = value.replace(old, new)
            return re.sub(r"S-1-5-21-\d+-\d+-\d+-\d+", "<HOST_ACCOUNT_SID>", value)
        return value
    return walk(raw)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-only", action="store_true", help="Verify public hashes/observations; explicitly skip ignored raw bytes")
    args = parser.parse_args()
    manifest = load(BASE / "pinned-manifest.json")
    assert manifest["schema"] == "S31_REPORT_EVIDENCE_V1" and manifest["final_run"] == 4
    for name, expected in manifest["artifacts_sha256"].items():
        assert Path(name).name == name, "Manifest may name adjacent files only"
        actual = (BASE / name).read_bytes()
        assert digest(actual) == expected, "Pinned hash mismatch: " + name
        text = actual.decode("utf-8")
        assert not re.search(r"(?i)[A-Z]:\\+Users\\+", text), "Host user path in public artifact: " + name
        assert not re.search(r"S-1-5-21-\d+-\d+-\d+-\d+", text), "Host account SID in public artifact: " + name
    for index in range(1, 5):
        record = load(BASE / ("run-%02d.stdout.json" % index))
        source_name = "appcontainer_probe.py" if index == 4 else "appcontainer_probe_run%02d.py" % index
        assert record["probe_sha256"] == manifest["artifacts_sha256"][source_name]
        assert record["helper_sha256"] == manifest["artifacts_sha256"]["windows_api.py"]
        assert (BASE / ("run-%02d.stderr.txt" % index)).read_bytes() == b""
        assert record["profile_folder_absent_after"] and record["profile_mapping_absent_after"] and record["owned_temp_removed"]
        if record["owned_profile_created_this_run"]:
            assert record["create_profile_hresult"] == "0x00000000" and record["delete_profile_hresult"] == "0x00000000"
        ledger = manifest["raw_derived_ledger"]["run-%02d" % index]
        assert record["private_raw_sha256"] == ledger["raw_sha256"]
        assert digest((BASE / ("run-%02d.stdout.json" % index)).read_bytes()) == ledger["public_sha256"]
        if not args.public_only:
            relative = Path(ledger["raw_relative_path"])
            assert relative.parts[:4] == ("studio", ".local", "review-raw", "S31") and len(relative.parts) == 5
            raw_bytes = (PRODUCT / relative).read_bytes()
            assert digest(raw_bytes) == ledger["raw_sha256"], "Raw hash mismatch"
            expected_public = redact_raw(json.loads(raw_bytes))
            assert {key: record[key] for key in expected_public} == expected_public, "Raw-to-public derivation mismatch"
    final = load(BASE / "run-04.stdout.json")
    assert load(BASE / "run-04.host.json")["host_exit"] == 0
    assert final["diagnostic_complete"] and final["marker"] == "GT02_S31_APPCONTAINER_DIAGNOSTIC_COMPLETE"
    assert final["profile_folder_absent_before"] and final["profile_mapping_absent_before"]
    assert final["profile_folder_exists_after_create"] and final["profile_mapping_exists_after_create"]
    assert final["profile_api_path_matches"]
    for mode in ("control", "appcontainer"):
        result = final[mode]
        assert result["host_captured_exit"] == 37 and result["wait_result"] == 0
        assert result["job_active_processes_after_wait"] == 0 and result["job_process_ids_at_final"] == []
        assert result["readback"]["child_started"] and result["readback"]["child_completed"] and result["readback"]["scratch_positive"]
    control, child = final["control"], final["appcontainer"]
    assert child["token_is_appcontainer"] == 1 and child["token_package_sid_matches"]
    assert child["integrity_sid"] == "S-1-16-4096" and child["capability_count"] == 0
    for key in ("private_read_observed", "private_write_changed", "private_delete_effect", "private_rename_effect", "private_hardlink_effect"):
        assert control["readback"][key] is True and child["readback"][key] is False
    assert child["readback"]["private_contents_unchanged"] and child["readback"]["private_link_count"] == 1
    assert final["safe_write"] == "UNSUPPORTED_SAFE_OPEN_WINDOWS"
    print(json.dumps({"verified": "S31_FIXED_COMMAND_DIAGNOSTIC_ONLY", "raw_derivation_verified": not args.public_only,
                      "artifact_count": len(manifest["artifacts_sha256"]), "safe_write": "UNSUPPORTED_SAFE_OPEN_WINDOWS",
                      "manifest_sha256": digest((BASE / "pinned-manifest.json").read_bytes()), "writes": 0}))

if __name__ == "__main__":
    main()
