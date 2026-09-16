# Managed declarative script eligibility

`script_profile.py` implements the candidate availability profile
`hh-godot-declarative-1`. It performs pure, byte-exact eligibility checks. It
does not parse through Godot, import a project, execute a script, inspect an
engine object, write files, grant capabilities or issue a public ACK. Eligibility
is not full section 2.3/GT-03 acceptance; coordinator and independent critics
must assess availability against the unchanged plan and DoD.

## Exact accepted source

Input must be an exact Python `bytes` value, valid UTF-8, at most 16,384 bytes.
The profile is ASCII only, with LF line endings and exactly one final LF. No
BOM, NUL, comments, blank lines, indentation, trailing spaces or CRLF are
accepted. The first line is exactly `extends Node3D`. Subsequent lines use
exactly one space at each position shown:

```gdscript
extends Node3D
@export var fixture_value: int = 23
@export var move_speed: float = 7.0
@export var turn_speed: float = 90.0
@export var enabled: bool = true
```

| Declaration | Required | Allowed literal |
| --- | --- | --- |
| `fixture_value: int` | yes | integer from -1,000,000 through 1,000,000 |
| `move_speed: float` | no | decimal from 0 through 100 |
| `turn_speed: float` | no | decimal from 0 through 360 |
| `enabled: bool` | no | `true` or `false` |

Names are unique and appear in this fixed order; optional declarations may be
omitted. No other declaration/name/type is accepted. Omitted values are absent
from result metadata, not silently defaulted.

Integer grammar is `0` or an optional minus followed by a nonzero ASCII digit
and zero or more ASCII digits. There is no plus sign, leading zero, underscore,
hex/binary spelling or exponent. `-0` is rejected.

Float grammar has a nonnegative integer part without leading zeros, a dot,
and a nonempty fractional part. Its fractional part is exactly `0`, or ends
in a nonzero digit: `7.0`, `0.125` and `90.01` are eligible; `7`, `.5`, `7.`,
`07.0`, `7.00`, `1e1` and `-0.0` are not. Range checks compare the original
decimal exactly, so rounding cannot admit an out-of-range value. The converted
binary64 value must be finite; a nonzero decimal that underflows to zero is
unsupported. Fraction length is bounded by the total source-byte cap. This
grammar rejects noncanonical spelling; it never normalizes submitted bytes.

Every original byte must match these complete lines. Methods, `@tool`, static
initializers/data, setters/getters, resource loads, `preload`, expressions,
class names, nested classes and script inheritance have no grammar production.
No keyword removal, substring blacklist, comment stripping or source rewriting
is used. Eligibility of a standalone script does not make an arbitrary scene
or its other resource dependencies eligible.

## API and error contract

`validate_script(raw: bytes) -> ValidatedScriptProfile` returns a frozen,
slotted dataclass with:

- `profile`: `hh-godot-declarative-1`.
- `source_bytes`: the exact original immutable bytes.
- `sha256`: lowercase SHA256 of those exact bytes, without a prefix.
- `declarations`: ordered tuple of frozen `ExportDeclaration` values with
  `name`, `gd_type`, `literal` and typed scalar `value`.
- `defaults`: a fresh `dict[name, scalar]` on every access. Mutating it cannot
  change the result. `int`, `float` and `bool` retain distinct Python types.

Keep both `gd_type` and `literal` when carrying metadata to engine validation;
canonical JSON may serialize a float such as `7.0` as `7`. The digest binds the
original script, not a reconstructed rendering. Direct construction of
`ValidatedScriptProfile(source_bytes)` performs the same checks; its derived
fields are not constructor arguments. Python object immutability is not an
isolation boundary against malicious code in the host process.

Rejection raises `ScriptProfileError` with a fixed `code` and diagnostic
`reason`, without reflecting submitted source:

- `BAD_SCRIPT_BYTES`: input is not exact `bytes`, exceeds the byte cap, or is
  not valid UTF-8. The byte cap is checked before decoding.
- `UNSUPPORTED_SCRIPT_PROFILE`: valid UTF-8 within the cap fails any profile
  rule, including empty input, non-ASCII, BOM/NUL, wrong formatting, unknown
  declarations or out-of-range/unsupported literal representation.

Neither rejected input nor eligible input carries parse/import PASS or a
publication receipt. This module has no filesystem or engine side effects.

## Required downstream proof

Before activation, a future owner must close and bind the complete scene/load
graph, project configuration, UID/source dependencies, trusted bootstrap and
pinned engine. It must run actual Linux sandbox parse/import, then trusted
fresh-process scene/script/hash and instance/export readback against those
exact bytes. Child markers and exit zero alone do not prove these checks.
Containment limits, complete stream drain, real exit/cleanup, Stop/deadline,
revision/lease and durable publication checks remain necessary. A broader
profile, including executable code hooks, needs its own explicit eligibility
and attribution proof; this profile must not silently fall back to it.

Pure tests: `python -B studio/tests/godot/test_script_profile.py` from
`8-9-hh3d-3/`. These tests establish eligibility behavior only, not Godot
acceptance or section 2.3 completion.
