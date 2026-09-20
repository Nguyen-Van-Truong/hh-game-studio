# S129 diagnostic helper repair — static evidence only

`AUTHORITY=0`; no GT-06 acceptance, plan tick, F13/F14 eligibility, engine run,
runtime edit or commit. This folder is the only write scope for this repair.
Baseline Git HEAD: `d81d58a3c7b8390b108abcf0da6c7d13188b3194`.
The working tree already contained unrelated changes; they were not edited.

The helper addresses the schema, boundary, role-binding and partial-row defects
documented in `../20260920-gt06-s128-host-attribution/helper-audit.md`. S128 remains
`INCOMPLETE_UNKNOWN`; these static tests neither reinterpret its missing receipts
nor establish a cause for its interruption. The separate launcher-supervision
gap remains outside this helper's scope. There is no launcher in this folder.

## Changes and integration contract

- PSS identity joins use `pid`, `process_start` and normalized `executable`, the
  actual adapter contract. PID/start must match the retained role. Executable
  must exist in every PSS identity and match any prior executable expectation.
- `validate_roles` is a pure joint-row/retained-probe binding check for both
  `host` and `editor`. It must run before supplemental observation. Host counter
  samples also have their `process` identity checked. The real retained
  `ProcessProbe` need not expose an executable attribute.
- PSS status, binding, cleanup, errors, identity, Stop and elapsed time are
  checked before a successful row is handed to the writer. Rows use schema
  `S129.post-failure-observation.1` and `observation_validated=true`.
- A role's `post-failure-<role>-complete.json` is written only after all four
  validated offsets (`0,1,3,5`). `validate_observation_packet` rejects missing or
  false completion, partial/reordered rows, stale schema, wrong binding,
  missing validation markers, invalid PSS joins and acceptance/dataset flags.
  Successful rows saved before a later failure remain partial evidence.
- `GateObserver` requires an explicit Boolean `stop_at_boundary`. `false`
  returns the original gate's value naturally through the configured count;
  `true` raises the diagnostic boundary only after the original gate passes.
  The original exception is re-raised with its original traceback even when
  binding, retained-probe lookup, supplemental capture or receipt writing fails.
  A rejected original gate is never appended to the passed-gates list.

The caller retains process ownership, immutable run/source/sample bindings,
durable atomic writes and an external deadline. This helper opens no processes
itself. Its completion validator is a structural diagnostic check, not proof
that files were durably written, a source/hash verifier or benchmark acceptance.
A packer must use the actual persisted rows and completion receipt, verify its
frozen expected binding and file hashes, and reject missing/conflicting/error
receipts; a row filename alone never proves a completed observation. Every
emitted record remains `formal_acceptance=false`, `eligible_for_dataset=false`.

S128's old launcher call is deliberately not edited. A future caller must pass
`stop_at_boundary=STOP_AT_BOUNDARY`, provide both retained-role probes, preserve
the original screen gate, and bind the helper/source hashes in its own fresh
execution manifest. No reuse of a previous diagnostic ID is authorized here.

## Provenance and tests

The supplied partial S129 helper before this repair had SHA-256
`ba58507a64fddc5853a0b5a92c297ae84deaf8b35d6b1e80c671cbcd55ac45fe`.
The tests read (and do not copy or modify) the actual S128 copied adapter:

`../20260920-gt06-s128-host-attribution/owned/gt06-s128-host-attribution-01/pss_adapter.py`

Its SHA-256 is pinned in the test:
`797398a54cac5f7c772df7ec9c5ad988fe9e54c26c3c10e172a768e39dc25c76`.
The production `_Native.identity` method builds the identity using a fake
kernel; the production `capture_owned` assembles the snapshot using its explicit
fake `_api`/`_clock` seams. No DLL is loaded, no target is opened, no engine is
started, no native PSS capture occurs, and test time advances virtually.
This directly covers the schema join that the historical self-check fabricated.

From the repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260920-gt06-s129-helper-repair/test_post_failure_handles.py
```

The initial 18 tests (archived byte-exact in `history-18-tests/`) cover production-shaped capture for both roles, PID/start/executable
mismatches, PSS failure states and cleanup, Stop/deadline/probe drift before
publishing, failed completion persistence, partial/tampered packet rejection,
host/editor binding, both boundary paths, role-specific dispatch, non-handle gate
failures, and primary exception identity/traceback preservation. Captured focused
test output, real child exit and file hashes are recorded beside this document.

## Final integration corrections

The current helper adds failed PSS payload preservation in a separate incomplete,
unvalidated receipt, independent per-role dispatch with observed/failed/skipped
outcomes, Stop checks before each role, and a single remaining-time calculation
that cannot request a negative sleep at an offset boundary. A failed editor
observation does not suppress host evidence; each role retains its original
8-second observation budget. Neither helper delay changes a passed gate.

Current validation is **26/26**, actual exit 0; `focused-tests-03/` retains raw
stdout/stderr and exact executing helper/test hashes. `focused-tests-02/` was
captured in Python text mode and is explicitly normalized text, not raw streams.
The top-level original focused-tests receipt is historical (18 tests); its
bound bytes are retained under history-18-tests. The integration caller must
provide its existing `check_stop` function to `GateObserver`.
