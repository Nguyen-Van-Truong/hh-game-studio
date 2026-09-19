# S115 — coupled journal boundary

AUTHORITY=0. One bounded diagnostic, excluded from F13/F14. No formal retry,
acceptance, repair or root-cause claim.

S114 completed an owned, seeded-history host-only batch without S110's timeout.
It observed no index rebuild during the batch. The next unresolved difference
is the full stock campaign's engine/host workload and accumulated batches.
S115 adds the same bounded wall/thread-CPU attribution to that combination.
It can distinguish snapshot/fsync/reload/rebuild intervals when a delay recurs;
a non-reproduction closes this experiment, not an automatic identical retry.

Run `python -B coupled_journal.py --check`, then `--launch` exactly once. The
output is `studio/.local/reviews/gt06-s115-coupled-01`. Existing output is an
error; never remove it to rerun the ID. The launcher copies its three helpers,
binds live runtime53 and copied helpers in the owned process manifest, and uses
the existing BenchmarkProcess with its original Job limits. Runtime/profile
bytes stay unchanged. Four no-engine tests verify original rejections and
cleanup errors cannot be swallowed by the diagnostic boundary.

The existing campaign child runs its unchanged import and original coupled
batches 0–6. The native benchmark file is byte-identical to stock S102. Only
the host Journal is subclassed to wrap original calls; no seed, native overlay,
threshold, heartbeat, deadline, journal durability or fault behavior changes.
The full original screen runs before counting a gate. Original failure stops
immediately; after the seventh successful gate a named boundary exception uses
the original failure/cleanup path. The outer work limit is 1,230 seconds with
owned cleanup afterward. Estimated diagnostic duration is 10–20 minutes.

`timing-summary.json`, `attempt/child-failure.json`,
`attempt/child-terminal-cleanup.json`, HTTP observation/phase files,
`owned/process-{start,exit}.json`, `owned/cleanup-*.json` and `result.json` must
be read together. Boundary child exit0 is a collector disposition, not native
success. Native natural exit can remain UNKNOWN after the owned boundary kill;
it must never inherit the helper's exit. All old S102/S110 errors remain open.
Retained cleanup errors make the child nonzero even at the planned boundary.

Timing wrappers add included overhead. Nested spans overlap; Python os.fsync
does not expose SQLite's internal sync. Low thread CPU plus high wall time
does not distinguish disk, GIL, lock wait, scheduling or memory pressure.
Do not subtract timings, move heartbeat, raise baselines, change priority,
trim/pin RAM or stop another application's processes.

Read liveness and short tails on the existing 10-minute heartbeat. While live,
freeze runtime/helper/profile/workstation and run no parallel engine, tests or
heavy hash audit. After terminal, preserve all raw and exact hashes before
choosing a repair or a next distinct boundary. No duplicated diagnostic run.

The S113 progress section was archived byte-exactly in `archive/`, with
SHA-256 and AUTHORITY=0; the main tools plan remains the only progress source.
The S114 packet writer finished all writes; its final console-only line-count
print failed because Windows used cp1252 for the Vietnamese archive. No engine
or measurement failed. Verify the existing packet instead of rerunning it.
