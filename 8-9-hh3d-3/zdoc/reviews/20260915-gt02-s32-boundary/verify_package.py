"""Read-only verification of pinned S32 diagnostics; no rerun or ledger rewrite."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
PRODUCT = BASE.parents[2]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def redact(raw):
    broker = re.search(r"O:(S-1-5-21-\d+-\d+-\d+-\d+)", raw["effective_sddl"]["scratch"]).group(1)
    replacements = [(raw["fixture_root"], "<OWNED_TEMP>"), (raw["profile_path"], "<OWNED_PROFILE_PATH>"),
                    (broker, "<BROKER_SID>"), (raw["package_sid"], "<APPCONTAINER_SID>"),
                    (raw["profile_name"], "<OWNED_PROFILE_NAME>"),
                    (str(Path(raw["profile_path"]).parents[3]), "<USER_PROFILE>"),
                    (str(PRODUCT), "<PRODUCT_ROOT>"),
                    (os.environ.get("SystemRoot", ""), "<SYSTEM_ROOT>"),
                    (os.environ.get("ProgramFiles(x86)", ""), "<PROGRAM_FILES_X86>")]
    def walk(value):
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str):
            for old, new in replacements:
                if old:
                    value = value.replace(old, new)
            return re.sub(r"S-1-5-21-\d+-\d+-\d+-\d+", "<HOST_ACCOUNT_SID>", value)
        return value
    return walk(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-only", action="store_true")
    args = parser.parse_args()
    manifest = read(BASE / "pinned-manifest.json")
    require(manifest["schema"] == "S32_REPORT_EVIDENCE_V1" and manifest["final_run"] == 5, "Wrong manifest")
    for name, expected in manifest["artifacts_sha256"].items():
        require(Path(name).name == name, "Adjacent artifact names only")
        data = (BASE / name).read_bytes()
        require(sha(data) == expected, "Pinned hash mismatch: " + name)
        require(not re.search(r"(?i)[A-Z]:\\+Users\\+", data.decode("utf-8")), "Host user path in public artifact")
        require(not re.search(r"S-1-5-21-\d+-\d+-\d+-\d+", data.decode("utf-8")), "Host account SID in public artifact")
    for index in range(1, 6):
        record = read(BASE / f"run-{index:02}.stdout.json")
        host = read(BASE / f"run-{index:02}.host.json")
        source = "boundary_probe.py" if index == 5 else f"boundary_probe_run{index:02}.py"
        native = "boundary_child.c" if index == 5 else f"boundary_child_run{index:02}.c"
        require(record["probe_sha256"] == manifest["artifacts_sha256"][source], "Probe source mismatch")
        require(record["native_source_sha256"] == manifest["artifacts_sha256"][native], "Native source mismatch")
        require(record["helper_sha256"] == manifest["artifacts_sha256"]["windows_api.py"], "Helper mismatch")
        require(host["run_id"] == record["run_id"] == f"GT02-S32-BOUNDARY-{index:02}", "Run ID mismatch")
        require(host["host_exit"] == (0 if index == 5 else 1), "Parent exit mismatch")
        require((BASE / f"run-{index:02}.stderr.txt").read_bytes() == b"", "Nonempty stderr")
        require(record["profile_folder_absent_after"] and record["profile_mapping_absent_after"] and record["owned_temp_removed"], "Owned cleanup missing")
        if record["owned_profile_created_this_run"]:
            require(record["create_profile_hresult"] == record["delete_profile_hresult"] == "0x00000000", "Profile API failure")
        if not args.public_only:
            relative = Path(record["private_raw_relative_path"])
            require(relative.parts[:4] == ("studio", ".local", "review-raw", "S32") and len(relative.parts) == 5, "Raw scope mismatch")
            raw = (PRODUCT / relative).read_bytes()
            require(sha(raw) == record["private_raw_sha256"], "Raw hash mismatch")
            expected = redact(json.loads(raw, object_pairs_hook=unique))
            require({key: record[key] for key in expected} == expected, "Redaction derivation mismatch")
            executable = Path(record["native_executable_private_relative"])
            require(executable.parts[:4] == relative.parts[:4] and len(executable.parts) == 5, "Native binary scope mismatch")
            require(sha((PRODUCT / executable).read_bytes()) == record["native_executable_sha256"], "Native executable mismatch")
    final = read(BASE / "run-05.stdout.json")
    require(final["diagnostic_complete"] and final["marker"] == "GT02_S32_BOUNDARY_DIAGNOSTIC_COMPLETE", "Final marker absent")
    require(final["profile_folder_absent_before"] and final["profile_mapping_absent_before"], "Profile not freshly owned")
    require(final["sentinel_bytes_unchanged"], "Broker sentinel changed")
    for mode, result in final["cases"].items():
        native, actual = result["native"], result["host_readback"]
        require(result["host_captured_exit"] == 47 and result["wait_result"] == 0, "Native exit mismatch")
        require(result["job_active_processes_after_wait"] == 0 and result["job_process_ids_at_final"] == [], "Live process tree")
        require(native["started"] == "S32_NATIVE_STARTED" and native["complete"] == "S32_NATIVE_COMPLETE", "Native completion missing")
        container = mode.startswith("appcontainer")
        require(result["token_is_appcontainer"] == int(container), "Wrong primary token")
        if container:
            require(result["token_package_sid_matches"] and result["integrity_sid"] == "S-1-16-4096" and result["capability_count"] == 0, "Wrong isolation token")
        for key in ("private_open_zero_error", "private_open_write_dac_error", "private_open_write_owner_error",
                    "directory_delete_child_open_error", "directory_add_file_open_error", "directory_add_subdirectory_open_error",
                    "private_create_directory_error", "private_delete_file_error", "broker_open_duplicate_handle_error",
                    "broker_open_vm_write_error", "broker_open_create_thread_error", "broker_open_create_process_error", "broker_open_query_limited_error"):
            require(native[key] == (5 if container else 0), "Access matrix mismatch: " + mode + "/" + key)
        require(actual["source_canary_unchanged"] and actual["created_directory_exists"] == (not container)
                and actual["delete_canary_exists"] == container, "Canary mismatch")
        require(native["sentinel_identity_matches"] == int(mode == "inherit_control"), "Leaked sentinel identity")
        if mode == "inherit_control":
            require(native["sentinel_payload_matches"] == 1, "Inherited positive control failed")
        else:
            require(native["sentinel_read_attempted"] == 0, "Unverified numeric handle read")
        restricted = mode == "appcontainer_restricted"
        require(native["child_policy_query_error"] == 0 and native["no_child_process_creation"] == int(restricted), "Child policy mismatch")
        require(native["child_create_success"] == int(not restricted), "Child creation mismatch")
        require(actual["child_marker_present"] == (not restricted), "Child marker mismatch")
        if restricted:
            require(native["child_create_error"] == 367, "Expected ERROR_CHILD_PROCESS_BLOCKED")
        else:
            require(native["child_host_captured_exit"] == 43 and actual["child_marker_matches"], "Child positive control failed")
    require(final["safe_write"] == "UNSUPPORTED_SAFE_OPEN_WINDOWS", "Unexpected capability claim")
    print(json.dumps({"verified": "S32_FIXED_NATIVE_BOUNDARY_ONLY", "artifacts": len(manifest["artifacts_sha256"]),
                      "raw_derivation_verified": not args.public_only, "safe_write": final["safe_write"], "writes": 0,
                      "manifest_sha256": sha((BASE / "pinned-manifest.json").read_bytes())}))


if __name__ == "__main__":
    main()
