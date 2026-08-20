#!/usr/bin/env python3
"""R0-WP4: policy.example.toml passes; invalid fixtures are rejected."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "godot"))

import policy_validate  # noqa: E402


def main() -> int:
    return policy_validate.self_test()


if __name__ == "__main__":
    sys.exit(main())
