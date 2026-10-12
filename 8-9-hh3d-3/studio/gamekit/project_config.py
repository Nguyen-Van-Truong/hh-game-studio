"""Surgical project.godot merging: only the command's setting keys may change.

Godot remains the value serializer.  This scanner only finds complete entries
(including multiline dictionaries/InputEvent objects) and preserves all source
text outside the requested keys.  Ambiguous or malformed syntax fails closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import common as C

_SECTION = re.compile(r"^\s*\[([^\[\]]+)\]\s*(?:[;#].*)?$")
_KEY = re.compile(r"^\s*([^\s=;#][^=]*?)\s*=")


@dataclass(frozen=True)
class Entry:
    section: str
    start: int
    end: int
    text: str


def _scan(value: str, stack: list[str], quoted: bool) -> bool:
    escaped = False
    for char in value:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char in ";#":
            break
        elif char == '"':
            quoted = True
        elif char in "([{":
            stack.append(char)
        elif char in ")]}":
            expected = {")": "(", "]": "[", "}": "{"}[char]
            if not stack or stack.pop() != expected:
                raise C.GamekitError("GODOT_FAILED", "unbalanced project.godot value")
    return quoted


def _document(data: bytes) -> tuple[list[str], dict[str, Entry], dict[str, int]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise C.GamekitError("GODOT_FAILED", "project.godot must be UTF-8") from exc
    lines = text.splitlines(keepends=True)
    entries: dict[str, Entry] = {}
    section_ends: dict[str, int] = {"": len(lines)}
    section = ""
    stack: list[str] = []
    quoted = False
    start = -1
    key = ""
    for index, line in enumerate(lines):
        if start >= 0:
            quoted = _scan(line, stack, quoted)
        else:
            plain = line.lstrip("\ufeff").strip()
            if not plain or plain.startswith((";", "#")):
                continue
            header = _SECTION.fullmatch(plain)
            if header:
                section_ends[section] = index
                section = header.group(1).strip()
                if section in section_ends:
                    raise C.GamekitError("GODOT_FAILED", f"duplicate project.godot section {section!r}")
                section_ends[section] = len(lines)
                continue
            match = _KEY.match(line.lstrip("\ufeff"))
            if not match:
                raise C.GamekitError("GODOT_FAILED", f"unsupported project.godot syntax at line {index + 1}")
            short_key = match.group(1).strip()
            key = f"{section}/{short_key}" if section else short_key
            if key in entries:
                raise C.GamekitError("GODOT_FAILED", f"duplicate project.godot key {key!r}")
            start = index
            quoted = _scan(line.lstrip("\ufeff")[match.end():], stack, False)
        if not stack and not quoted:
            entries[key] = Entry(section, start, index + 1, "".join(lines[start:index + 1]))
            start = -1
    if start >= 0:
        raise C.GamekitError("GODOT_FAILED", f"unfinished project.godot value for {key!r}")
    if "config_version" not in entries:
        raise C.GamekitError("GODOT_FAILED", "project.godot has no config_version")
    return lines, entries, section_ends


def preserved_entries(data: bytes, changed_keys: set[str]) -> dict[str, str]:
    """Exact source entries outside a command's write set, for postconditions."""
    _, entries, _ = _document(data)
    # Adding a section may supply the missing final line terminator; the entry
    # itself must remain identical, including all multiline value text.
    return {key: entry.text.rstrip("\r\n") for key, entry in entries.items() if key not in changed_keys}


def require_preserved(original: bytes, current: bytes, changed_keys: set[str]) -> None:
    """Verify the saved source outside the write set after the native readback."""
    if preserved_entries(original, changed_keys) != preserved_entries(current, changed_keys):
        raise C.GamekitError("READBACK_MISMATCH", "project.godot changed outside the command write set")


def merge_project_godot(original: bytes, generated: bytes, *, drop_keys: set[str]) -> bytes:
    """Take only owned keys from Godot output; retain every other source byte.

    Missing owned keys are deliberate removals.  Callers separately check that
    requested additions exist and do a fresh Godot readback before committing.
    Generated changes to config/features or defaults are ignored.
    """
    source_lines, source, section_ends = _document(original)
    _, output, _ = _document(generated)
    changed = set(drop_keys)
    if "config_version" in changed:
        raise C.GamekitError("BAD_REQUEST", "commands cannot change config_version")
    edits: list[tuple[int, int, str]] = []
    additions: dict[str, list[str]] = {}
    newline = "\r\n" if any(line.endswith("\r\n") for line in source_lines) else "\n"
    for key in sorted(changed):
        old = source.get(key)
        new = output.get(key)
        value = "" if new is None else new.text.replace("\r\n", "\n").replace("\n", newline)
        if value and not value.endswith(("\n", "\r")):
            value += newline
        if old is not None:
            edits.append((old.start, old.end, value))
        elif new is not None:
            additions.setdefault(new.section, []).append(value)
    appended: list[str] = []
    for section, values in additions.items():
        if section in section_ends:
            at = section_ends[section]
            prefix = newline if at and not source_lines[at - 1].endswith(("\r", "\n")) else ""
            edits.append((at, at, prefix + "".join(values)))
        else:
            appended.append(newline + f"[{section}]" + newline + "".join(values))
    merged = list(source_lines)
    # For a shared index, replace an existing entry before inserting a new one.
    for start, end, value in sorted(edits, key=lambda row: (row[0], row[1]), reverse=True):
        merged[start:end] = [value] if value else []
    data = ("".join(merged) + "".join(appended)).encode("utf-8")
    if preserved_entries(original, changed) != preserved_entries(data, changed):
        raise C.GamekitError("GODOT_FAILED", "project.godot changed outside the command write set")
    return data
