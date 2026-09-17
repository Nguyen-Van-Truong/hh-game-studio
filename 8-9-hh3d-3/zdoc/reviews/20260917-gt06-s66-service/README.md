# GT-06 S66 service progress — not acceptance

GT-01 through GT-05 remain accepted. GT-06 remains in progress.
The prior input/fault/managed-repair/replay milestone is checkpoint `3186d40`.

The new authenticated service binds a prepared immutable runtime, registered
grant and lease, typed command, source/snapshot/trace hashes, and durable intent.
Start is ACCEPTED_PENDING until actual native completion/readback. Inspection
is explicitly historical; this is not a live debugger. Stop and lookup retain
separate HTTP capacity and a stopped connection cannot resume work.

`runs.json` binds the retained local raw artifacts and driver for two real
Godot/HTTP runs. Both use source closure
`2c623754803e14d59f5d143b3964443a73d21eadaf5947d91fd4a83423e34da2`.

- `gt06-s66-service-complete-01`: 13 distinct checks, including native completion,
  durable duplicate replay without a second runtime, paginated PAUSED inspection,
  and hash-bound MENU capture. Repeated lookup polls are not extra scenarios.
- `gt06-s66-service-stop-01`: 11 distinct checks, native Stop while running,
  CANCELED rather than false COMMITTED, reconnect denial, and owned-tree drain.
  Stop receipt took 25.0122 ms in this single run. This is not a p95 benchmark.
- Both actual child/wrapper exits are zero; owned trees verified, stderr empty,
  driver unchanged. Native source hashes match frozen per-file maps.
- `unit-capture.json` and `unit-invocation.json`: 243 tests passed, no skips,
  actual child/wrapper exits zero, clean owned tree, listed sources unchanged.

Regressions cover command-ID collisions leaving the original pending receipt
intact, grant rotation requiring a fresh lease, failed completion resolving to
UNKNOWN, and durable terminal receipts taking precedence over an uncertain
in-memory observation. Preparation failure retains the cleanup owner.

Remaining GT-06 work includes reviewer UX, congested/revoked/stale native lanes,
the full declared benchmark, final frozen source/evidence matrix and two fresh
independent reviews. Neither these tests nor the S65 diagnostics close GT-06.

Reproduce with a fresh unique run ID using
`studio/tests/replay/run_service_probe.py --run-id gt06-... --mode complete|stop`
inside the bounded `studio/build/bootstrap/run_fixture.py` host runner.
Do not overwrite retained run directories or reuse old signatures.
