# S97 reader evidence packet preparation

AUTHORITY=0. Diagnostic implementation/evidence review, not a final critic,
benchmark acceptance, S96 causal finding, memory result or plan tick.

`seal_reader_regressions.py` is prepared only. This worker has not executed,
compiled or tested it, launched an engine, edited the frozen harness/runtime,
or changed any original run artifact. Coordinator execution is still required.

The fixed selection is 24 cases: START/ACK multiplied by the twelve cases in
the frozen harness. `reader-selection.json` is root-editable and deliberately
has `writers_stopped=false` until the coordinator confirms terminal state.
The packer refuses that pending selection. It also requires the exact matrix
histories and original per-case terminal evidence; setting the flag alone
cannot turn missing or mismatched evidence into a sealed packet.

The three driver versions remain distinct:

| Evidence | Driver SHA-256 |
|---|---|
| START normal01 | `6233514e57b02429bad477200454c3033f324622d5cd289dda4cae1ed88eaee1` |
| Matrix01's four executed cases | `4dd5cdaf79a41e8dfec195d77c61be8a4b51911774c7bb3030da0fbcf7bbe880` |
| Matrix02's remaining 19 cases and metadata revalidator | `88e4df1040b31a3239057759e8d85d89cdb71a9d2b38b17d8e7c4ce9988611fe` |

All cases must bind native candidate
`13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`
and harness `4265d17f1767f6f95602a09d7444fdba5dca50dd7237439b833515092e43db91`.
The source map excluding only the Python driver must remain identical across
cases. Every declared source byte is checked against its retained snapshot.
Every fixed project file is checked against both its executed copy and retained
snapshot, including the exact test-only two-line short-read overlay/reversal.
No current driver bytes are substituted for the older normal01 snapshot.

Each import/native process record is joined to actual process-start/exit JSON,
the capture's artifact hashes and original cleanup receipt. Jobs must be
zero/closed/untainted and process handles released; native/helper negatives
must retain exit 86. They are successful rejection coverage, never PASS-native.
The separate outer run_fixture capture must join its actual host-exit receipt,
correct stage/case/run argv and owned-tree status.

The only permitted collector correction is START malformed01. Its original
outer exit **1**, `completed=false`, sole `READER_NATIVE_STDERR` error and
native/helper exit **86** remain mandatory. Exact six-line parser stderr is
derived from the frozen reader/harness source locations. The independent
derived artifact is pinned to
`1ef2b2e863efc8d312e91c5c07496cdd2b41080e4b2c0f3939ad1c3d494130cd`
and joined to its original artifact hashes and actual metadata-revalidator
exit 0 in `reader-revalidation-owned-02`. The earlier `-01` prelaunch-aborted
record is also retained. There is no generic allow-failed option.

The packet keeps exact per-case results, freezes, logs, exit/cleanup receipts,
input/output files and outer records. Repeated source/project-source bytes are
stored once at `source-pool/<sha256>`, with explicit logical raw locators,
hashes, sizes and packet paths in the inventory. Runtime caches (`.godot`,
owner appdata/localappdata/temp/blender-user, bytecode) are excluded. Evidence
reads are capped at 16 MiB per file, 512 MiB total and 12,000 entries. The
bootstrap source is checked against its declared unchanged pin and pooled;
engine/Python executable identities remain captured hashes, not bundled binaries.

After terminal confirmation, root sets only `writers_stopped=true`, reviews
the selection, and runs from the repository root (use a new output suffix if
an attempt already exists):

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s97-ack-recovery/seal_reader_regressions.py --selection 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s97-ack-recovery/reader-selection.json --output 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s97-ack-recovery/reader-validation-packet-01
```

Packing includes a second verification from only packet bytes. A later portable
verification can run without the original raw folders:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s97-ack-recovery/seal_reader_regressions.py --verify-packet 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s97-ack-recovery/reader-validation-packet-01
```

Failures exit 1 and preserve an exclusive `failure.json`; existing packets are
never overwritten. No source imports, subprocesses or process operations occur.
This packet covers the authored reader matrix, which bypasses production boot
admission and uses fixture deadlines. Absence-to-pending, post-validation
deadline crossing and owned Stop while pending are not added coverage. Pending
memory counters remain observations only. Full coupled behavior and historical
ObjectDB growth still require their own evidence.
