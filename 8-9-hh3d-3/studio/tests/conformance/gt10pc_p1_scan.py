"""P1 member-byte scan: no monetization surface and no armed failpoint ships.

The manifest flags are builder-written; this scan reads every archive member
instead and is recomputed by the matrix verifier from the archive bytes.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path, PurePosixPath

from studio.package.release_contract import digest_bytes, digest_file, need

SCHEMA = "hh-gt10pc-p1-scan-2"
PAYMENT = re.compile(rb"(?i)voucher|refund|chargeback|purchase|payment|billing|storekit|stripe|paypal|"
                     rb"admob|unityads|ironsource|applovin|wallet|subscription|in[-_]app[-_]?(?:purchase|billing)")
# The policy gate itself names the flag; nothing else may mention it.
POLICY_MEMBERS = frozenset({"manifest.json", "payload/studio/package/release_contract.py"})
MONETIZATION = re.compile(rb"(?i)monetiz")
FAILPOINT_FILES = re.compile(r"(?i)gt07-failpoint(?:-reached)?\.json")
ARM_SCHEMAS = frozenset({"HH-GT07-FAILPOINT-1", "HH-GT07-FAILPOINT-REACHED-1"})
# The scan and its unit test must spell the terms they reject. Each is exempt
# from the term checks only while byte-identical to the copy running the scan.
_HERE = Path(__file__).resolve()
SELF_MEMBERS = {
    "payload/studio/tests/conformance/" + _HERE.name: _HERE,
    "payload/studio/tests/conformance/test_gt10pc_p1_scan.py": _HERE.with_name("test_gt10pc_p1_scan.py"),
}


def _self_member(name: str, data: bytes) -> bool:
    source = SELF_MEMBERS.get(name)
    return source is not None and source.is_file() and source.read_bytes() == data


def _arm_config(name: str, data: bytes) -> bool:
    """Harness code may name the schema; only a shipped arm/reached document arms."""
    if not name.lower().endswith(".json") or b"HH-GT07-FAILPOINT" not in data:
        return False
    try:
        value = json.loads(data)
    except ValueError:
        return True
    return isinstance(value, dict) and value.get("schema") in ARM_SCHEMAS


def scan_archive(path: Path) -> dict:
    payment, monetization, armed, exempt = [], [], [], {}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            data = archive.read(name)
            if _self_member(name, data):
                exempt[name] = digest_bytes(data)
            else:
                if PAYMENT.search(data):
                    payment.append(name)
                if MONETIZATION.search(data) and name not in POLICY_MEMBERS:
                    monetization.append(name)
            parts = PurePosixPath(name).parts
            if FAILPOINT_FILES.fullmatch(parts[-1]) or ".local" in parts or _arm_config(name, data):
                armed.append(name)
    need(not payment, "GT10PC_P1_PAYMENT_SURFACE:" + ",".join(payment[:5]))
    need(not monetization, "GT10PC_P1_MONETIZATION_SURFACE:" + ",".join(monetization[:5]))
    need(not armed, "GT10PC_P1_FAILPOINT_ARMED:" + ",".join(armed[:5]))
    return {"schema": SCHEMA, "archive_sha256": digest_file(path), "members": len(names),
            "payment_members": 0, "monetization_members": 0, "armed_failpoints": 0,
            "exempt_self": exempt, "status": "PASS"}
