# GT07–GT10 read-only preparation — S175

`RUN_ID=gt07-10-readonly-prep-01`

`COMMAND_ID=cmd.gt07-10.readonly-prep.1`

`AUTHORITY=0`

`STATUS=PREPARATION_ONLY`

This package is a static preparation map only. GT07, GT08, GT09 and GT10
remain `PLANNED` and unopened. It does not run Godot, Blender, CDB, Android,
CI, package installation, or any acceptance workload, and it cannot advance a
checkbox or substitute for GT06 acceptance.

## Dependency order

1. GT06 must first be accepted with attribution authority, the full 10 fresh
   host/editor pairs × 35 batches, complete dataset/hash/exit/tree/job/handle
   evidence, and two same-hash critics.
2. GT07 then verifies scheduling, lease/FIFO/expiry/fencing, bounded
   concurrency, cross-app activation and crash/recovery transactions.
3. GT08 consumes GT07 and verifies clean Windows/Linux/Android import/export,
   cache/build matrix and CI. A physical Android device is a hard gate; an
   emulator cannot replace it.
4. GT09 consumes GT08 and verifies full client/agent conformance on isolated
   fixture clones, including unsupported-version, lease-conflict and
   prompt/tool-output safety cases.
5. GT10 consumes GT09 and verifies package install, upgrade, rollback,
   revocation/security floor, uninstall preservation and handoff.

## Gate inventory from the authoritative plan

- **GT07:** FIFO/expiry/fencing/dependency/bounded concurrency; two writers on
  one `.blend`/`.tscn`; expired-lease late result; terminate/Stop/crash;
  rollback must preserve a newer manual edit; logs must not expose tokens.
- **GT08:** clean Windows/Linux/Android export and cache matrix; TQ08-B and
  TX16-C; physical Android runtime/GPU proof is mandatory.
- **GT09:** TX01–TX18 conformance on isolated clones; unsupported client
  version; concurrent lease edits and recovery; measured adapter path; no
  claim based on an unrun model or a fixture-only shortcut.
- **GT10:** TQ08-I/TX16-I; clean-copy install, upgrade, rollback, revocation,
  uninstall without deleting art/game, compatibility/support runbook and
  release manifest.

## Resume rule

Do not dispatch or tick any GT07–GT10 work from this package while GT06 is
open. On a future GT06 acceptance, use fresh IDs and a new source/evidence
freeze, then execute exactly one bounded gate at a time with actual exits,
cleanup and same-hash critic review.
