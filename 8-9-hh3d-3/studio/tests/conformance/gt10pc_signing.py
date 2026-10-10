"""Local publisher helper. Excluded from shipped runtime/verification payload.

The test key is generated once into a private .local directory. There is no
seed in source. The verifier receives a separately pinned public trust file.
"""
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def load_signer(private_path: Path, expected_public: bytes):
    raw = private_path.read_bytes()
    if len(raw) != 32:
        raise ValueError("GT10PC_PUBLISHER_PRIVATE_LENGTH")
    key = Ed25519PrivateKey.from_private_bytes(raw)
    if key.public_key().public_bytes_raw() != expected_public:
        raise ValueError("GT10PC_PUBLISHER_TRUST_MISMATCH")
    return key.sign
