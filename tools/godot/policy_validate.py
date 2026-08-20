#!/usr/bin/env python3
"""Validate HH Godot Agent policy files (R0-WP4). Stdlib only.

Rejects: path `..`, absolute paths outside the LocalAppData jail, arbitrary
shell, credential-shaped values. Allows placeholders such as YOUR_TOKEN_HERE.

  python tools/godot/policy_validate.py .hh-agent/policy.example.toml
  python tools/godot/policy_validate.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover — 3.11+ required
    print("policy_validate: Python 3.11+ required (tomllib)", file=sys.stderr)
    raise SystemExit(2)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_POLICY = REPO_ROOT / ".hh-agent" / "policy.example.toml"
FIXTURE_DIR = REPO_ROOT / "tests" / "bootstrap" / "policy"

SCHEMA = "hh-godot-agent-policy/1"
PROFILES = {"OBSERVE", "EDIT", "OWNER_AUTOPILOT"}
PROCESS_CANON = {"godot", "gut", "exporter", "git"}
PROCESS_ALIASES = {
    "godot": "godot",
    "godot_console": "godot",
    "godot_headless": "godot",
    "gut": "gut",
    "gut_cli": "gut",
    "exporter": "exporter",
    "godot_export": "exporter",
    "git": "git",
}
GODOT_TAG = "4.7.1-stable"
GODOT_VERSION_ID = "4.7.1.stable.official.a13da4feb"
STOP_GATES = (
    "E1_secret_or_account",
    "E2_spend_or_paid_quota",
    "E3_sign_upload_publish_or_exfil",
    "E4_brief_contradiction_or_product_pivot",
)
PATH_KEY_HINTS = (
    "root",
    "dir",
    "path",
    "rel",
    "jail",
    "location",
    "local_app_data",
    "allow_write",
    "deny_write",
    "export_out",
)
ALLOWED_ABS_PREFIXES = (
    "%LOCALAPPDATA%/HHGodotAgent",
    "%LOCALAPPDATA%\\HHGodotAgent",
    "${LOCALAPPDATA}/HHGodotAgent",
    "${LOCALAPPDATA}\\HHGodotAgent",
)
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
PLACEHOLDER_RE = re.compile(
    r"^(YOUR_[A-Z0-9_]+_HERE|REPLACE_ME|CHANGEME|<[^>]+>|PLACEHOLDER)$",
    re.IGNORECASE,
)
# High-entropy-ish credential prefixes. Do not match prose `sk-` / `ghp_`.
SK_RE = re.compile(r"\bsk-[A-Za-z0-9]{20,}")
GHP_RE = re.compile(r"\bghp_[A-Za-z0-9]{20,}")
# Quoted TOML/JSON/env `token = "..."` — not code like `let token = self.foo`.
TOKEN_QUOTED_RE = re.compile(
    r"(?i)\b([A-Za-z0-9_]*token)\s*=\s*[\"']([^\"']+)[\"']"
)
TOKEN_UNQUOTED_RE = re.compile(
    r"(?i)\b([A-Za-z0-9_]*token)\s*=\s*(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,})"
)
SECRET_BLOB_RE = re.compile(r"^[A-Za-z0-9+/=_\-]{20,}$")

FIXTURE_EXPECT = {
    "fail_path_dotdot.toml": "E_PATH_DOTDOT",
    "fail_path_absolute.toml": "E_PATH_ABSOLUTE",
    "fail_arbitrary_shell.toml": "E_ARBITRARY_SHELL",
    "fail_secret.toml": "E_SECRET",
    "fail_addon_jail.toml": "E_ADDON_JAIL",
}
# §6.4: generic write cannot touch the Godot addon host or hh_agent plugin.
# Spellings are aliased: res://addons/** ↔ godot/plugin-project/addons/**.
REQUIRED_DENY_PREFIXES = (
    "addons/hh_agent/",
    "res://addons/",
    "godot/plugin-project/addons/",
)
PLUGIN_PROJECT_PREFIX = "godot/plugin-project/"
JAIL_ATTACK_ALLOWS = (
    "res://addons/godot-mcp/",
    "res://godot/plugin-project/addons/godot-mcp/",
    "godot/plugin-project/./addons/godot-mcp/",
    "godot/plugin-project//addons/godot-mcp/",
    "Godot/plugin-project/addons/godot-mcp/",
    "godot\\\\plugin-project\\\\addons\\\\godot-mcp/",
    "godot/plugin-project/addons./godot-mcp/",
    "godot/plugin-project./addons/godot-mcp/",
    "godot/plugin-project/addons.../godot-mcp/",
)


def posixish(s: str) -> str:
    return s.replace("\\", "/")


def is_path_key(key: str) -> bool:
    k = key.lower()
    return any(h in k for h in PATH_KEY_HINTS)


def has_dotdot(s: str) -> bool:
    return any(part == ".." for part in posixish(s).split("/"))


def is_os_absolute(s: str) -> bool:
    t = s.strip()
    if not t or t in {".", "./"}:
        return False
    if t.startswith("res://"):
        return False
    if t.startswith("%") or t.startswith("${"):
        return True
    if t.startswith("//") or t.startswith("\\\\"):
        return True
    if len(t) >= 3 and t[0].isalpha() and t[1] == ":" and t[2] in "\\/":
        return True
    if t.startswith("/"):
        return True
    return Path(t).is_absolute()


def win32_component(part: str) -> str:
    """Win32 strips trailing dots and spaces from a path segment (not '.' / '..')."""
    if part in (".", ".."):
        return part
    return part.rstrip(" .")


def collapse_posix(s: str) -> str:
    """Lowercase POSIX path; drop empty and '.' segments; keep '..' for other checks.

    Do not use str.lstrip('./') — that strips any mix of those characters.
    """
    raw = s.replace("\\", "/").strip()
    scheme = ""
    rest = raw
    if raw.lower().startswith("res://"):
        scheme = "res://"
        rest = raw[6:]
    while rest.startswith("./") or rest.startswith("/"):
        rest = rest[2:] if rest.startswith("./") else rest[1:]
    parts: list[str] = []
    for part in rest.split("/"):
        part = win32_component(part)
        if part in ("", "."):
            continue
        parts.append(".." if part == ".." else part.lower())
    body = "/".join(parts)
    return scheme + body


def as_prefix(s: str) -> str:
    p = collapse_posix(s)
    if not p:
        return ""
    return p if p.endswith("/") else p + "/"


def path_aliases(s: str) -> set[str]:
    """res://addons/** and godot/plugin-project/addons/** are the same host."""
    p = as_prefix(s)
    if not p:
        return set()
    out = {p}
    if p.startswith("res://"):
        rest = p[6:]
        out.add(as_prefix(PLUGIN_PROJECT_PREFIX + rest))
        out.add(as_prefix(rest))
    elif p.startswith(PLUGIN_PROJECT_PREFIX):
        rest = p[len(PLUGIN_PROJECT_PREFIX) :]
        out.add(as_prefix("res://" + rest))
        out.add(as_prefix(rest))
    elif p.startswith("addons/"):
        out.add(as_prefix("res://" + p))
        out.add(as_prefix(PLUGIN_PROJECT_PREFIX + p))
    return {item for item in out if item}


def prefix_covers(deny: str, required: str) -> bool:
    """True if deny is the required path, a parent, or an aliased spelling."""
    for deny_a in path_aliases(deny):
        for req_a in path_aliases(required):
            if req_a == deny_a or req_a.startswith(deny_a):
                return True
    return False


def path_under(path: str, prefix: str) -> bool:
    """True if path equals prefix, is a child, or matches an aliased spelling."""
    for path_a in path_aliases(path):
        for prefix_a in path_aliases(prefix):
            if path_a == prefix_a or path_a.startswith(prefix_a):
                return True
    return False


def abs_allowlisted(s: str) -> bool:
    n = posixish(s.strip())
    for prefix in ALLOWED_ABS_PREFIXES:
        p = posixish(prefix)
        if n == p or n.startswith(p + "/"):
            return True
    return False


def find_secrets(text: str) -> list[tuple[str, int, str]]:
    """Return (code_detail, line_no, snippet) for credential-shaped text."""
    hits: list[tuple[str, int, str]] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if SK_RE.search(line):
            hits.append(("sk-", i, stripped[:120]))
        if GHP_RE.search(line):
            hits.append(("ghp_", i, stripped[:120]))
        for match in TOKEN_QUOTED_RE.finditer(line):
            value = match.group(2)
            if PLACEHOLDER_RE.match(value):
                continue
            if SK_RE.search(value) or GHP_RE.search(value) or SECRET_BLOB_RE.match(value):
                hits.append(("token=", i, stripped[:120]))
        if TOKEN_UNQUOTED_RE.search(line):
            hits.append(("token=", i, stripped[:120]))
    return hits


def walk_strings(obj: Any, key_stack: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], str]]:
    out: list[tuple[tuple[str, ...], str]] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            out.extend(walk_strings(val, key_stack + (str(key),)))
    elif isinstance(obj, list):
        for val in obj:
            out.extend(walk_strings(val, key_stack))
    elif isinstance(obj, str):
        out.append((key_stack, obj))
    return out


def canon_process(name: str) -> str | None:
    n = name.strip().lower()
    if n.endswith(".exe"):
        n = n[:-4]
    return PROCESS_ALIASES.get(n)


def validate_policy_text(text: str, source: str = "<policy>") -> list[str]:
    errors: list[str] = []
    for detail, line_no, snippet in find_secrets(text):
        errors.append(
            f"E_SECRET: {source}:{line_no} credential-shaped {detail!r}: {snippet}"
        )
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return [f"E_TOML: {source}: {exc}"]

    schema = data.get("schema")
    if schema != SCHEMA:
        errors.append(f"E_SCHEMA: {source}: expected {SCHEMA!r}, got {schema!r}")

    profile = data.get("profile")
    if not isinstance(profile, dict):
        errors.append(f"E_PROFILE: {source}: missing [profile]")
    else:
        name = profile.get("name")
        if name not in PROFILES:
            errors.append(f"E_PROFILE: {source}: name must be one of {sorted(PROFILES)}")
        if profile.get("allow_profile_escalation") is not False:
            errors.append(f"E_PROFILE: {source}: allow_profile_escalation must be false")

    gates = data.get("stop_gates")
    if not isinstance(gates, dict):
        errors.append(f"E_GATES: {source}: missing [stop_gates]")
    else:
        for key in STOP_GATES:
            if gates.get(key) is not True:
                errors.append(f"E_GATES: {source}: {key} must be true (E1–E4 stop)")

    roots = data.get("roots")
    if not isinstance(roots, dict):
        errors.append(f"E_ROOTS: {source}: missing [roots]")
    else:
        for flag in (
            "block_dotdot",
            "block_symlink_escape",
            "block_junction_escape",
            "block_device_reserved",
        ):
            if roots.get(flag) is not True:
                errors.append(f"E_ROOTS: {source}: {flag} must be true (A8 jail)")
        deny_rel = roots.get("deny_write_rel")
        if not isinstance(deny_rel, list):
            errors.append(f"E_ADDON_JAIL: {source}: deny_write_rel must be an array")
            deny_rel = []
        deny_strs = [item for item in deny_rel if isinstance(item, str)]
        for required in REQUIRED_DENY_PREFIXES:
            if not any(prefix_covers(item, required) for item in deny_strs):
                errors.append(
                    f"E_ADDON_JAIL: {source}: deny_write_rel must cover {required!r}"
                )
        allow_rel = roots.get("allow_write_rel")
        if isinstance(allow_rel, list):
            for item in allow_rel:
                if not isinstance(item, str):
                    continue
                for required in REQUIRED_DENY_PREFIXES:
                    if path_under(item, required):
                        errors.append(
                            f"E_ADDON_JAIL: {source}: allow_write_rel {item!r} "
                            f"cannot punch through deny {required!r}"
                        )

    proc = data.get("process")
    if not isinstance(proc, dict):
        errors.append(f"E_PROCESS: {source}: missing [process]")
    else:
        if proc.get("allow_arbitrary_shell") is not False:
            errors.append(
                f"E_ARBITRARY_SHELL: {source}: allow_arbitrary_shell must be false"
            )
        if proc.get("args_are_arrays") is not True:
            errors.append(f"E_PROCESS: {source}: args_are_arrays must be true")
        allow = proc.get("allowlist")
        if not isinstance(allow, list) or not allow:
            errors.append(f"E_PROCESS: {source}: allowlist must be a non-empty array")
        else:
            mapped: set[str] = set()
            for item in allow:
                if not isinstance(item, str):
                    errors.append(f"E_PROCESS: {source}: allowlist entries must be strings")
                    continue
                canon = canon_process(item)
                if canon is None:
                    errors.append(
                        f"E_ARBITRARY_SHELL: {source}: process {item!r} is not "
                        f"godot/gut/exporter/git"
                    )
                else:
                    mapped.add(canon)
            missing = PROCESS_CANON - mapped
            if missing:
                errors.append(
                    f"E_PROCESS: {source}: allowlist missing {sorted(missing)}"
                )
        godot = proc.get("godot")
        if isinstance(godot, dict):
            tag = godot.get("tag")
            if tag is not None and tag != GODOT_TAG:
                errors.append(
                    f"E_GODOT_PIN: {source}: tag must be {GODOT_TAG!r}, got {tag!r}"
                )
            ver = godot.get("version_id")
            if ver is not None and ver != GODOT_VERSION_ID:
                errors.append(
                    f"E_GODOT_PIN: {source}: version_id must be {GODOT_VERSION_ID!r}"
                )

    retention = data.get("retention")
    if not isinstance(retention, dict):
        errors.append(f"E_RETENTION: {source}: missing [retention]")
    else:
        for key in ("evidence_days", "ledger_days"):
            val = retention.get(key)
            if not isinstance(val, int) or val <= 0:
                errors.append(f"E_RETENTION: {source}: {key} must be a positive int")
        if retention.get("ledger_in_git") is not False:
            errors.append(f"E_RETENTION: {source}: ledger_in_git must be false")

    auth = data.get("auth")
    if not isinstance(auth, dict):
        errors.append(f"E_AUTH: {source}: missing [auth] (A9 loopback+token)")
    else:
        bind = auth.get("bind")
        if bind not in LOOPBACK:
            errors.append(f"E_AUTH: {source}: bind must be loopback, got {bind!r}")
        if auth.get("allow_non_loopback") is not False:
            errors.append(f"E_AUTH: {source}: allow_non_loopback must be false")
        if auth.get("log_secrets") is not False:
            errors.append(f"E_AUTH: {source}: log_secrets must be false (A9)")
        token = auth.get("session_token")
        if isinstance(token, str) and token and not PLACEHOLDER_RE.match(token):
            errors.append(
                f"E_SECRET: {source}: session_token must be a placeholder "
                f"(YOUR_TOKEN_HERE), never a live token"
            )

    pause = data.get("pause")
    if isinstance(pause, dict) and pause.get("always_available") is not True:
        errors.append(f"E_PAUSE: {source}: pause.always_available must be true")

    for keys, value in walk_strings(data):
        if not value or not is_path_key(keys[-1] if keys else ""):
            continue
        label = ".".join(keys) if keys else "path"
        if has_dotdot(value):
            errors.append(f"E_PATH_DOTDOT: {source}: {label} contains '..': {value!r}")
        if is_os_absolute(value) and not abs_allowlisted(value):
            errors.append(
                f"E_PATH_ABSOLUTE: {source}: {label} is absolute outside "
                f"allowlist: {value!r}"
            )

    return errors


def validate_policy_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"E_IO: {path}: {exc}"]
    try:
        rel = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        rel = str(path)
    return validate_policy_text(text, rel)


def self_test() -> int:
    errors: list[str] = []
    if not EXAMPLE_POLICY.is_file():
        print(f"FAIL: missing {EXAMPLE_POLICY}", file=sys.stderr)
        return 1
    example_errs = validate_policy_file(EXAMPLE_POLICY)
    if example_errs:
        errors.append("policy.example.toml must pass, got:")
        errors.extend(f"  {e}" for e in example_errs)

    if not FIXTURE_DIR.is_dir():
        errors.append(f"missing fixture dir {FIXTURE_DIR}")
    else:
        seen: set[str] = set()
        for fixture in sorted(FIXTURE_DIR.glob("fail_*.toml")):
            seen.add(fixture.name)
            expect = FIXTURE_EXPECT.get(fixture.name)
            got = validate_policy_file(fixture)
            codes = {item.split(":", 1)[0] for item in got}
            if not got:
                errors.append(f"{fixture.name}: expected reject, but passed")
            elif expect and expect not in codes:
                errors.append(
                    f"{fixture.name}: expected {expect} among {sorted(codes)}: {got}"
                )
        missing = set(FIXTURE_EXPECT) - seen
        if missing:
            errors.append(f"missing fixtures: {sorted(missing)}")

    example_text = EXAMPLE_POLICY.read_text(encoding="utf-8")
    needle = '  "godot/",'
    if needle not in example_text:
        errors.append("policy.example.toml missing allow_write_rel godot/ needle")
    else:
        for attack in JAIL_ATTACK_ALLOWS:
            mutated_allow = example_text.replace(
                needle, needle + f'\n  "{attack}",', 1
            )
            synth_jail = validate_policy_text(
                mutated_allow, f"<jail-attack:{attack}>"
            )
            if not any(e.startswith("E_ADDON_JAIL:") for e in synth_jail):
                errors.append(
                    f"jail attack allow {attack!r} was not rejected: {synth_jail}"
                )

    fake_sk = "sk-" + ("ab" * 16)
    fake_ghp = "ghp_" + ("cd" * 18)
    mutated = EXAMPLE_POLICY.read_text(encoding="utf-8")
    mutated = mutated.replace(
        'session_token = "YOUR_TOKEN_HERE"',
        f'session_token = "{fake_sk}"\ntoken = "{fake_ghp}"',
    )
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".toml",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(mutated)
        tmp_path = Path(tmp.name)
    try:
        synth = validate_policy_text(mutated, tmp_path.name)
        if not any(e.startswith("E_SECRET:") for e in synth):
            errors.append(f"synthesized sk-/ghp_/token= fixture was not rejected: {synth}")
    finally:
        tmp_path.unlink(missing_ok=True)

    if errors:
        print("FAIL: policy self-test", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print("PASS: policy.example.toml valid; fail fixtures rejected")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="policy TOML to validate",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="example must pass; tests/bootstrap/policy/fail_*.toml must fail",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.path is None:
        parser.error("provide a policy path or --self-test")
    errs = validate_policy_file(args.path)
    if errs:
        print(f"FAIL: {args.path}", file=sys.stderr)
        for item in errs:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print(f"PASS: {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
