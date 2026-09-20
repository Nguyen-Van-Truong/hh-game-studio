# S133 execution-binding reader candidate

Preparatory implementation only; AUTHORITY=0, formal acceptance false, final
critics pending. No runtime files or historical manifests are changed. No binding
artifact is minted here. Tests were held while S132 was live and executed only
after the coordinator confirmed that measurement was terminal.

`binding_candidate.py` accepts one fixed internal binding with exactly three keys:

```json
{
  "schema": "HH-GT06-EXECUTION-BINDING-1",
  "accepted_gt05_manifest_sha256": "fd0b4a984c7bee261c083c07d461baf55325e936d66df2eeab897b422ee0a02b",
  "source_files": {"studio-relative/source.py": "64 lowercase hex digits"}
}
```

The example is schema illustration, not an executable candidate. The installed
coordinator supplies the exact-byte SHA256 from its frozen release record, the
historical source map obtained through the untouched pinned GT05 input verifier,
and a nonempty `frozenset` of mandatory current dependencies. Do not accept those
arguments from HTTP, tool requests, environment overrides or candidate JSON.

Avoid a hash cycle by keeping the fixed trusted release selector outside the
binding's source-map domain. The selector and binding still belong in the final
execution/run/request closure. Reader and native-runner source may be included in
the binding. Preserve the existing ordering that appends generated `run.json` to
the final run map after the immutable source/snapshot map has been constructed.

Every historical GT05 source key remains required; its old digest remains in the
old manifest. The new map pins current bytes and may add required dependencies.
Unknown/missing dependencies, invalid paths, case aliases, reparse paths, malformed
JSON and hash changes fail closed. Current source mismatch preserves the existing
`REPLAY_REUSE_SOURCE_CHANGED` error. Run/source freezes, input artifact checks,
native ownership, postconditions and final acceptance remain caller obligations.

The isolated test entrypoint is `python -B test_binding_candidate.py -v`. It uses
temporary synthetic files only; it never starts an engine or touches runtime
manifests. On 2026-09-20 at 09:14:04–09:14:05 UTC, all 17 tests passed with actual
Python exit 0. `tests-01.capture.json` retains the executable/argv, timestamps,
before/after source hashes and exact log hashes; stdout is empty and unittest's
normal verbose results are in `tests-01.stderr.txt`.

The earlier reader-only attempt had these exact-file hashes (unchanged during
that attempt; the reader was subsequently factored for the installed selector):

- Reader: `cfbb49e088c45529d8f4ec8f96adc0a4ef9e69fd1a5aba93bc02629a383e5aa3`.
- Tests: `72ddbfc3baf50ffbd4a6d5660498e8291d49dfa5cc1b038e191b59ab4addbde6`.

## Installed selector candidate

`installed_candidate.load_installed(studio, accepted_source_files)` uses only
`host/replay/execution-current.json` and `host/replay/execution-source.json`.
The selector has exactly `schema: HH-GT06-EXECUTION-SELECTION-1` and
`binding_sha256`; it has no path, source map or request override. The returned
sorted map contains the verified current source map plus separate exact-byte
hashes for both metadata files. Both metadata paths, including case variants,
are forbidden inside the binding's source map.

Required dependencies include the inherited GT05 paths, toolchain lock and owned
bootstrap runner; recursive Godot-addon, host/core and protocol source domains;
every top-level host/replay Python file; the perf schema and replay profile; and
the explicit observe/play fixture resource domains. `__pycache__` is excluded.
Inventory changes during verification reject, as do new dependencies missing
from the binding. Existing source and metadata bytes retain their strict checks.

`selection_identity(studio)` returns both strict metadata hashes without reading
runtime source files. The coordinator must latch this identity at native-runner
module import before other runtime imports, then compare the identity returned
in every verified map with that latch. A changed generation requires a fresh
interpreter. The pure reader deliberately keeps no global latch across synthetic
roots. When installing these drafts under runtime module names, adjust the
explicit sibling `binding_candidate` import accordingly and validate that
integration on its own frozen source.

The combined candidate suite ran once at 09:19:23–09:19:29 UTC on 2026-09-20:
33/33 passed, actual Python exit 0, no engine. `tests-02.capture.json` contains
the exact discovery argv, transcript hashes and unchanged before/after hashes:

- Reader: `7999c9e21b2f82a385e40dcfcad6d7e34cb7e46143b96423fa0ac4cd18d5c872`.
- Reader tests: `72ddbfc3baf50ffbd4a6d5660498e8291d49dfa5cc1b038e191b59ab4addbde6`.
- Installed loader: `ce4639456146ea0afba6eefd5a07fd87dfdf66da036b3891ecae0b225e0fb1e3`.
- Installed tests: `2ccd9a70db08606e7fd78794952a8ba76c4607bedbbbd87c9dc6a12f43f5c200`.

Integration remains pending. The coordinator must provide complete fixed
entrypoint/child/data dependency sets, retain the original GT05 payload verifier,
freeze the installed selector and candidate binding, integrate the same reader in
native/backend/repair entrypoints, and keep existing launch/postcondition checks.
These tests exercise reparse/symlink rejection through injected stat flags; they
do not certify adversarial filesystem race resistance. No current native
functional lane, GT05 republication, benchmark, final critic or acceptance result
is supplied by this isolated reader test suite.
