#!/usr/bin/env python3
"""Read-only DbgEng vtable contract checker for S166.

This tool intentionally does not start a process, load dbgeng.dll, attach a
debugger, or write evidence.  It parses the installed SDK header and checks
the literal vtable calls in the retained S162-S165 sources.  A passing result
proves only static slot consistency; it never proves debugger attribution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


INTERFACES = {
    "client": "IDebugClient",
    "control": "IDebugControl",
    "systems": "IDebugSystemObjects",
}

METHOD_MACRO = re.compile(r"^\s*STDMETHOD(?:V)?_?\s*\((?P<args>[^)]*)\)")
CALL = re.compile(
    r"\b(?:M|Method)\s*<\s*(?P<delegate>[A-Za-z_]\w*)\s*>\s*"
    r"\(\s*(?P<object>[A-Za-z_]\w*)\s*,\s*(?P<index>\d+)\s*\)"
)
KNOWN_HISTORICAL_INVALID = {
    "20260922-gt06-s164-dbgeng-index-repair": {
        ("WaitForEventDelegate", 90),
        ("ExecuteDelegate", 63),
    },
    "20260922-gt06-s165-dbgeng-process-selection": {
        ("WaitForEventDelegate", 90),
        ("ExecuteDelegate", 63),
    },
}
NONCODE = re.compile(r'@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/', re.DOTALL)


def code_only(text: str) -> str:
    """Mask comments/strings while preserving offsets and line numbers."""
    return NONCODE.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def interface_body(text: str, name: str) -> str:
    text = code_only(text)
    marker = f"DECLARE_INTERFACE_({name}, IUnknown)"
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"missing interface marker: {name}")
    opening = text.find("{", start)
    if opening < 0:
        raise ValueError(f"missing interface body: {name}")
    depth = 0
    for pos in range(opening, len(text)):
        char = text[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : pos]
    raise ValueError(f"unterminated interface body: {name}")


def interface_methods(text: str, name: str) -> list[str]:
    """Parse the supported STDMETHOD forms used by the Windows SDK header."""
    methods: list[str] = []
    body = interface_body(text, name)
    for line in body.splitlines():
        # Interface declarations put one macro invocation at the beginning of
        # a line.  Taking the final comma-separated item handles
        # STDMETHOD_(ULONG, AddRef), while STDMETHODV(Output) remains intact.
        match = METHOD_MACRO.match(line)
        if not match:
            continue
        args = [part.strip() for part in match.group("args").split(",")]
        method = args[-1] if args else ""
        if not re.fullmatch(r"[A-Za-z_]\w*", method):
            raise ValueError(f"unsupported STDMETHOD declaration in {name}: {line.strip()}")
        methods.append(method)
    if len(methods) != len(re.findall(r"\bPURE\s*;", body)):
        raise ValueError(f"unparsed interface method declaration in {name}")
    if methods[:3] != ["QueryInterface", "AddRef", "Release"]:
        raise ValueError(f"{name} does not begin with IUnknown slots: {methods[:3]}")
    if len(methods) != len(set(methods)):
        raise ValueError(f"duplicate method in {name}")
    return methods


def source_calls(path: Path, methods_by_interface: dict[str, list[str]]) -> list[dict[str, object]]:
    text = code_only(path.read_text(encoding="utf-8"))
    # The retained harnesses have one generic helper declaration, M<T> or
    # Method<T>. Every other use must be a literal invocation we can inspect.
    candidates = list(re.finditer(r"\b(?:M|Method)\s*<\s*(?!T\s*>)[A-Za-z_]\w*\s*>\s*\(", text))
    matches = list(CALL.finditer(text))
    if len(candidates) != len(matches) or not matches:
        raise ValueError(f"unparsed or absent vtable calls in {path}")
    calls: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for match in CALL.finditer(line):
            delegate = match.group("delegate")
            object_name = match.group("object")
            index = int(match.group("index"))
            interface = INTERFACES.get(object_name)
            method = re.sub(r"Delegate$", "", delegate)
            item: dict[str, object] = {
                "file": str(path),
                "line": line_number,
                "delegate": delegate,
                "object": object_name,
                "interface": interface,
                "requested_slot": index,
                "delegate_method": method,
                "slot_method": None,
                "valid": False,
            }
            if interface is None:
                item["error"] = "unbound_object"
            elif not delegate.endswith("Delegate"):
                item["error"] = "unsupported_delegate_name"
            else:
                methods = methods_by_interface[interface]
                if index >= len(methods):
                    item["error"] = "slot_out_of_range"
                else:
                    item["slot_method"] = methods[index]
                    item["valid"] = methods[index] == method
                    if not item["valid"]:
                        item["error"] = "slot_name_mismatch"
            calls.append(item)
    return calls


def verify(header: Path, sources: Iterable[Path]) -> dict[str, object]:
    header = header.resolve()
    text = header.read_text(encoding="utf-8")
    methods = {name: interface_methods(text, name) for name in set(INTERFACES.values())}
    source_paths = [path.resolve() for path in sources]
    if not source_paths:
        raise ValueError("at least one source is required")
    calls = [call for path in source_paths for call in source_calls(path, methods)]
    errors = [call for call in calls if not call["valid"]]
    expected_invalid: list[dict[str, object]] = []
    unexpected_invalid: list[dict[str, object]] = []
    for call in errors:
        parent = Path(str(call["file"])).parent.name
        key = (str(call["delegate"]), int(call["requested_slot"]))
        if key in KNOWN_HISTORICAL_INVALID.get(parent, set()):
            expected_invalid.append(call)
        else:
            unexpected_invalid.append(call)
    static_pass = not unexpected_invalid
    return {
        "schema": "HH-GT06-S166-DBGENG-CONTRACT-1",
        "authority": 0,
        "formal_acceptance": False,
        "engine_started": False,
        "attribution_proven": False,
        "process_exit": "NOT_APPLICABLE_STATIC_AUDIT",
        "header": str(header),
        "header_sha256": sha256(header),
        "interface_slot_counts": {name: len(items) for name, items in methods.items()},
        "interface_prefixes": {name: items[:3] for name, items in methods.items()},
        "source_sha256": {str(path): sha256(path) for path in source_paths},
        "calls_checked": len(calls),
        "calls_valid": len(calls) - len(errors),
        "calls_invalid_expected_historical": expected_invalid,
        "calls_invalid_unexpected": unexpected_invalid,
        "pass": static_pass,
        "next_action": (
            "S162/S163 literal slots are consistent; S164/S165 contain the recorded invalid 90/63 experiment. "
            "Keep debugger attribution UNKNOWN and do not rerun index experiments."
            if static_pass
            else "Repair only the unclassified static contract errors before any admissible runtime attempt."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--header", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path, action="append")
    args = parser.parse_args()
    result = verify(args.header, args.source)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
