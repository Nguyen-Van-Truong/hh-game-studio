"""Verify saved S30 observations; no fixture mutation or child launch."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
PRODUCT = BASE.parents[2]

def read(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    acl, publish = read("restricted-acl-05.stdout.json"), read("handle-publish-06.stdout.json")
    for prefix, data, script, marker in (
        ("restricted-acl-05", acl, "restricted_acl_probe.py", "GT02_S30_RESTRICTED_ACL_OBSERVATIONS_COMPLETE"),
        ("handle-publish-06", publish, "handle_publish_probe.py", "GT02_S30_HANDLE_PUBLISH_OBSERVATIONS_COMPLETE"),
    ):
        assert read(prefix + ".host.json")["host_exit"] == 0
        assert (BASE / (prefix + ".stderr.txt")).read_bytes() == b""
        assert data["probe_sha256"] == sha(BASE / script)
        assert data["marker"] == marker and data["owned_temp_removed"] and "error" not in data
    full, write = acl["cases"][1:]
    assert all(code == 5 for code in full["source_opens_winerror"].values())
    assert full["scratch_create_winerror"] == 0 and full["private_delete_winerror"] == 5 and full["private_rename_winerror"] == 5
    assert write["private_delete_winerror"] == 0 and write["private_rename_winerror"] == 0
    assert acl["write_restricted_delete_effect_readback"] and acl["write_restricted_rename_effect_readback"]
    assert acl["preexisting_handle_effect_readback"] == "AFTER!"
    assert acl["primary_process"]["host_captured_exit"] == 0xC0000142
    assert acl["primary_process"]["child_result"] == "MISSING" and acl["primary_process"]["job_active_processes_after_wait"] == 0
    assert publish["win32_root_relative_publish"]["winerror"] == 87
    assert publish["create_only_publish"]["success"] and publish["same_source_identity"] and publish["same_volume"]
    assert publish["post_publish_identity"]["links"] == 1 and publish["post_publish_identity"]["reparse_tag"] == 0
    assert publish["write"]["readback_sha256"] == publish["post_publish_readback_sha256"]
    assert publish["create_only_collision"]["winerror"] == 183 and publish["collision_kept_destination"] and publish["collision_kept_source"]
    assert publish["replace_while_target_open"]["winerror"] == 5 and publish["replace_after_target_identity_changed"]["success"]
    assert publish["post_publish_identity"]["file_id"] != publish["changed_target_identity_before_replace"]["file_id"]
    source = PRODUCT / "studio/host/core/safe_open.py"
    expected_source_hash = "efc083f1c4fa875d3f748602924a05712aa60fed3abcdb46d058672930201535"
    assert sha(source) == expected_source_hash
    manifest = read("source-manifest.json")
    for group in ("scripts_sha256", "evidence_sha256"):
        for name, expected in manifest[group].items():
            assert sha(BASE / name) == expected, name
    scripts = manifest["scripts_sha256"]
    assert manifest["scripts_manifest_sha256"] == hashlib.sha256(json.dumps(scripts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "observations_verified": True,
              "production_safe_write": "UNSUPPORTED_SAFE_OPEN_WINDOWS", "atomic_replace": False,
              "primary_worker_execution": "UNPROVEN_STATUS_DLL_INIT_FAILED", "appcontainer": "NOT_RUN",
              "reparse_swap_and_file_id_open": "NOT_TESTED", "global_leftover_zero": False,
              "earlier_owned_temp_cleanup_denied": "[TEMP]\\gt02-s30-restricted-acl-y920imcz",
              "current_two_fixture_cleanup_verified": True, "scripts_manifest_sha256": manifest["scripts_manifest_sha256"]}
    (BASE / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
