# GT-02 protocol core candidate

Implemented a typed envelope layer in `studio/protocol/`, including the
vendored Apache-2.0 `rfc8785` pure-Python implementation.
It provides deterministic UTF-8 JSON with duplicate-key, lone-surrogate,
non-finite-number, depth, size and unsafe-integer rejection; versioned
`Request`, `Response`, `Capability` and `Discovery` records; operation/target
and payload hash binding; secret-field rejection; and a project-root path
resolver that fails closed on traversal, absolute/UNC/device/ADS paths and
symlink/reparse components. No transport, network, eval, process launch or
mutation is included.

Envelope parsers reject unknown fields (rather than silently accepting typos),
which keeps extension negotiation explicit and prevents downgrade ambiguity.
Request readback accepts only its derived `digest` field in addition to the
required envelope and verifies it against operation/target/payload/schema.

## Verification

```
python -m unittest discover -s 8-9-hh3d-3/studio/tests/protocol -v
python -m py_compile 8-9-hh3d-3/studio/protocol/core.py
```

Result: **12 tests passed, 2 symlink tests skipped because this Windows host
does not permit symlink creation; py_compile passed.** Existing
`studio/host/core/limits.py` tests also pass and remain outside this worker's
write scope.

## Integration limits

The canonical profile uses RFC 8785 JCS number rendering and UTF-16 property
ordering, with no Unicode normalization. The host limits layer imports the same
profile and schema; cross-module tests cover the shared envelope. A Node/Godot
golden-vector consumer is still required before adapter release.
`resolve_project_path` is lexical/read protection only;
safe writes still require the platform-specific handle primitive and must be
rejected when unavailable. Session tokens, lease/journal persistence,
transport authentication and mutation remain host responsibilities.
