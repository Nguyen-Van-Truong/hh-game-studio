# Godot JCS consumer

`jcs_godot.gd` independently serializes validated JSON values to RFC 8785 UTF-8
bytes and SHA-256. It does not call Python, Node, `JSON.stringify`, or a decimal
parser to render numbers. `golden_consumer.gd` is a trusted test runner, not a
command adapter or wire-admission API. It performs no game/editor mutation.

The binary64 converter expands the significand and its rounding interval using
exact integer arithmetic in decimal limbs. It selects the shortest decimal
inside that interval, prefers the nearest candidate and ties to even, then
applies ECMAScript's fixed/exponent notation thresholds. Unequal spacing at
powers of two and the subnormal boundary are handled explicitly. Property
sorting compares unsigned UTF-16 code units; strings retain their original
Unicode scalar values and use the RFC's control-character escaping.

Godot 4.7.2 cannot preserve U+0000 in a native `String`: `JSON.parse` replaces it
with U+FFFD and logs an error. `ScalarString` therefore stores Unicode scalar
values as integers, and `ObjectPairs` supports these strings as property names.
Both representations reject invalid scalars; object pairs reject duplicate
keys. Native strings, arrays and dictionaries remain supported for values they
can represent. This keeps U+0000 in the JCS profile rather than excluding it.

The fixture harness converts original Python fixture values to a tagged tree:
binary64 bytes, integer decimal text, Unicode codepoints, arrays and object
pairs. Expected canonical text and expected hashes are **not** sent to Godot.
Godot independently constructs and serializes those values. Node independently
parses the source fixtures and decodes the numeric bit vectors. Python, Node
and Godot must produce the same text, UTF-8 bytes and SHA-256 for every row,
including the separate request-body digest and payload digest.

Run from the repository root:

```powershell
python -m unittest discover -s 8-9-hh3d-3/studio/tests/protocol -p test_golden_vectors.py -v
```

The test locates the console executable from `HH_STUDIO_GODOT_CONSOLE`, the
existing local toolchain override, or the lock's conventional local directory.
Both the console and GUI companion hashes and `--version` must match
`studio/toolchain.lock.json`. Each run creates an isolated temporary project,
freezes its input files, launches one bounded process, captures its actual host
exit and diagnostics, checks path-scoped leftovers and verifies unchanged input
hashes. Setting `HH_GT02_GOLDEN_EVIDENCE_DIR` retains the host record under a
unique filename. A timeout, hash mismatch or runtime diagnostic fails the test;
an unavailable supported runtime is explicitly `SKIP_ENVIRONMENT`.

This evidence proves serialization of the same values across runtimes. It does
**not** prove strict parsing of untrusted raw JSON in Godot. Godot's built-in
parser is unsuitable for that boundary because it accepts trailing commas and
other non-JSON syntax, loses duplicate property names and cannot preserve NUL.
Before exposing a Godot adapter, the original bytes still require strict wire
validation, scalar-preserving decoding and domain/schema/capability checks.
Do not treat this runner or tagged fixture decoder as those production checks.

References:

- [RFC 8785 sections 3.2 and Appendix B](https://www.rfc-editor.org/rfc/rfc8785.html)
- [Godot JSON parser and serializer limitations](https://docs.godotengine.org/en/stable/classes/class_json.html)
