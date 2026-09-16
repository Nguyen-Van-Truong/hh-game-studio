"""Pure eligibility for a closed declarative script profile, not Godot validation.

No source rewriting, resource loading, I/O, engine execution or public receipt.
Every submitted byte must match the profile before any Godot process sees it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import math
import re


PROFILE = 'hh-godot-declarative-1'
MAX_SCRIPT_BYTES = 16 * 1024
_INTEGER = re.compile(r'(?:0|-?[1-9][0-9]*)\Z', re.ASCII)
_FLOAT = re.compile(r'(?:0|[1-9][0-9]*)\.(?:0|[0-9]*[1-9])\Z', re.ASCII)
_DECLARATION = re.compile(r'@export var ([a-z_]+): (int|float|bool) = ([^\n]+)\Z', re.ASCII)
_RULES = (
    ('fixture_value', 'int', -1_000_000, 1_000_000),
    ('move_speed', 'float', 0, 100),
    ('turn_speed', 'float', 0, 360),
    ('enabled', 'bool', None, None),
)


class ScriptProfileError(ValueError):
    """A rejected byte envelope or unsupported profile; neither means validation."""

    def __init__(self, code: str, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(f'{code}: {reason}')


def _unsupported(condition: bool, reason: str) -> None:
    if not condition:
        raise ScriptProfileError('UNSUPPORTED_SCRIPT_PROFILE', reason)


@dataclass(frozen=True, slots=True)
class ExportDeclaration:
    name: str
    gd_type: str
    literal: str
    value: int | float | bool


def _literal(text: str, gd_type: str, lower: int | None, upper: int | None) -> int | float | bool:
    if gd_type == 'bool':
        _unsupported(text in ('true', 'false'), 'boolean literal')
        return text == 'true'
    if gd_type == 'int':
        _unsupported(len(text) <= 8 and _INTEGER.fullmatch(text) is not None, 'integer literal')
        value = int(text)
        _unsupported(lower <= value <= upper, 'integer range')
        return value
    _unsupported(_FLOAT.fullmatch(text) is not None, 'float literal')
    # Compare the original decimal exactly before converting to binary64. A
    # rounded 100.00000000000000001 must not bypass the upper bound of 100.
    exact = Decimal(text)
    _unsupported(Decimal(lower) <= exact <= Decimal(upper), 'float range')
    value = float(text)
    _unsupported(math.isfinite(value) and (value != 0.0 or exact == 0), 'float representation')
    return value


def _parse(raw: bytes) -> tuple[ExportDeclaration, ...]:
    if type(raw) is not bytes:
        raise ScriptProfileError('BAD_SCRIPT_BYTES', 'exact bytes required')
    if len(raw) > MAX_SCRIPT_BYTES:
        raise ScriptProfileError('BAD_SCRIPT_BYTES', 'byte limit')
    try:
        source = raw.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        raise ScriptProfileError('BAD_SCRIPT_BYTES', 'invalid UTF-8') from None
    _unsupported(source.isascii(), 'ASCII profile')
    _unsupported(source.endswith('\n'), 'final LF required')
    lines = source.split('\n')
    _unsupported(3 <= len(lines) <= 6 and lines[-1] == '', 'declaration count')
    _unsupported(lines[0] == 'extends Node3D', 'native base declaration')
    declarations = []
    last_index = -1
    for line in lines[1:-1]:
        match = _DECLARATION.fullmatch(line)
        _unsupported(match is not None, 'export declaration grammar')
        name, gd_type, literal = match.groups()
        indices = [index for index, rule in enumerate(_RULES) if rule[0] == name]
        _unsupported(len(indices) == 1, 'export name')
        index = indices[0]
        _unsupported(index > last_index, 'unique fixed declaration order')
        rule = _RULES[index]
        _unsupported(gd_type == rule[1], 'export type')
        declarations.append(ExportDeclaration(name, gd_type, literal, _literal(literal, gd_type, rule[2], rule[3])))
        last_index = index
    _unsupported(bool(declarations) and declarations[0].name == 'fixture_value', 'required fixture_value')
    return tuple(declarations)


@dataclass(frozen=True, slots=True)
class ValidatedScriptProfile:
    """Immutable byte-exact eligibility result. Construction also validates."""

    source_bytes: bytes
    sha256: str = field(init=False)
    declarations: tuple[ExportDeclaration, ...] = field(init=False)
    profile: str = field(default=PROFILE, init=False)

    def __post_init__(self) -> None:
        declarations = _parse(self.source_bytes)
        object.__setattr__(self, 'declarations', declarations)
        object.__setattr__(self, 'sha256', hashlib.sha256(self.source_bytes).hexdigest())

    @property
    def defaults(self) -> dict[str, int | float | bool]:
        """Fresh scalar mapping; omitted declarations have no invented default."""
        return {declaration.name: declaration.value for declaration in self.declarations}


def validate_script(raw: bytes) -> ValidatedScriptProfile:
    """Accept exact profile bytes or raise; does not prove parse/import/readback."""
    return ValidatedScriptProfile(raw)
