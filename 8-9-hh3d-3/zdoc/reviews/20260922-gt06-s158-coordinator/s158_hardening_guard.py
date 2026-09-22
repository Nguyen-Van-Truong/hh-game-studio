"""Static safety gate for the retained S157 diagnostic candidates.

This module is deliberately review-only.  It never starts Godot, Blender,
BenchmarkProcess, or any child process.  It prevents a future coordinator
from dispatching the S157 candidate until its manifest/receipt contracts are
made strict enough for a bounded diagnostic.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path


RESERVED_PSS_FIELDS = {
    "creation_time_filetime",
    "granted_access",
    "handle_count",
    "pointer_count",
    "paged_pool_charge",
    "nonpaged_pool_charge",
}


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"missing function: {name}")


def _names(node: ast.AST) -> set[str]:
    return {item.id for item in ast.walk(node) if isinstance(item, ast.Name)}


def audit_launcher(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    authenticate = _function(tree, "authenticate")
    summary = _function(tree, "_summary_matches")
    boundary = _function(tree, "_boundary_code")
    findings: list[dict] = []

    # The child script is selected from an absolute helper_root, but its
    # digest is not required to be in execution-source-files.json.  A future
    # launch could therefore execute an unpinned helper while all listed
    # source files still match.
    auth_names = _names(authenticate)
    if "helper_root" in auth_names and "CHILD_SCRIPT" not in auth_names:
        findings.append({
            "code": "HELPER_NOT_PINNED",
            "severity": "BLOCKER",
            "evidence": "authenticate validates execution map entries but does not bind helper_root/CHILD_SCRIPT bytes",
        })

    # A boundary summary must prove the observed prefix and the actual target
    # PID.  The retained candidate only compares common binding fields.
    summary_names = _names(summary)
    boundary_names = _names(boundary)
    if "screened_batches" not in summary_names or "pid" not in summary_names:
        findings.append({
            "code": "SUMMARY_PREFIX_PID_NOT_BOUND",
            "severity": "BLOCKER",
            "evidence": "_summary_matches does not bind screened_batches or summary pid to the target receipt",
        })
    if "screened_batches" not in boundary_names:
        findings.append({
            "code": "BOUNDARY_PREFIX_NOT_REQUIRED",
            "severity": "BLOCKER",
            "evidence": "_boundary_code can classify a synthetic boundary without a non-empty original-gate prefix",
        })

    return {
        "eligible_to_dispatch": not any(item["severity"] == "BLOCKER" for item in findings),
        "findings": findings,
        "source": str(path),
    }


def audit_attribution_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    fields = set(spec.get("persisted_fields_per_entry", []))
    reserved = sorted(fields & RESERVED_PSS_FIELDS)
    return {
        "eligible_to_dispatch": not bool(reserved),
        "reserved_fields": reserved,
        "source": str(path),
        "reason": "Microsoft documents PSS_HANDLE_ENTRY CreationTime, GrantedAccess, HandleCount, PointerCount, PagedPoolCharge and NonPagedPoolCharge as reserved for OS use; they cannot support temporal attribution.",
    }


def run(root: Path) -> dict:
    launcher = root / "20260922-gt06-s157-launcher" / "diagnostic_launcher_s157.py"
    spec = root / "20260922-gt06-s157-attribution" / "diagnostic-spec.json"
    launcher_result = audit_launcher(launcher)
    attribution_result = audit_attribution_spec(spec)
    return {
        "schema": "HH-S158-hardening-review-1",
        "authority": 0,
        "formal_acceptance": False,
        "eligible_for_dataset": False,
        "engine_execution": "FORBIDDEN",
        "launcher": launcher_result,
        "attribution": attribution_result,
        "next_action": "Do not dispatch S157 candidate. Build a fresh helper with pinned helper bytes, prefix/target-PID bindings, and attribution fields limited to documented PSS data.",
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.root), ensure_ascii=False, sort_keys=True, indent=2))
