"""Load an externally pinned public trust document; never trust package keys."""
from pathlib import Path
from .release_contract import strict_json, digest_bytes, need
try:
    from build.bootstrap.install_toolchain import safe_path
except ModuleNotFoundError:
    from studio.build.bootstrap.install_toolchain import safe_path


def load_trust(path: Path, *, expected_sha256: str) -> dict[str, bytes]:
    with safe_path(path).open("rb") as stream:
        raw = stream.read(4097)
    need(len(raw) <= 4096 and digest_bytes(raw) == expected_sha256, "external trust pin mismatch")
    doc = strict_json(raw)
    need(isinstance(doc, dict) and set(doc) == {"schema", "key_id", "public_key_hex"}
         and doc["schema"] == "hh-local-publisher-trust-1", "external trust schema")
    need(isinstance(doc["key_id"], str) and 0 < len(doc["key_id"]) <= 120
         and isinstance(doc["public_key_hex"], str) and len(doc["public_key_hex"]) == 64,
         "external trust key invalid")
    try:
        public = bytes.fromhex(doc["public_key_hex"])
    except ValueError as exc:
        raise ValueError("external trust key encoding") from exc
    return {doc["key_id"]: public}
