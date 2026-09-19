# S100 copied-history HTTP attribution

AUTHORITY=0. Prepared only until the coordinator explicitly launches; no formal
acceptance, benchmark dataset, engine run, root-cause or no-leak claim.

The fixed fresh `run-01` uses current source51 (including `campaign.load_fixture()`
imports) and exact S98 postterminal journal bytes. It creates a new project and
producer and runs up to twenty existing ten-command diagnostic groups (200 mix
commands plus their setup/lookup/cancel traffic), with the original 105-second
owned target cap. It does not reconstruct the pre-failure batch17 history or
S98 residency/coupled workstation. Do not overwrite or reuse this run directory.

Launch only after coordinator serialization/preflight:

```powershell
& 'C:/Users/truon/AppData/Local/Programs/Python/Python311/python.exe' -B '8-9-hh3d-3/zdoc/reviews/20260919-gt06-s100-recovery/http-attribution/run_probe.py' --launch
```

`prepared-manifest.json` pins helper hashes, source51, Python and historical
input. The launcher refuses a changed source/helper/history and independently
freezes/copied-hashes inputs, then captures actual target/helper exits and owned
Job cleanup through the existing runner. Its narrower cleanup evidence does not
replace a separate retained-handle observer. Timeout/missing target receipt is
incomplete; a zero tree is not an exit receipt. No old source or evidence changes.

The exact S95 phase helper is copied and pinned. All client/server/journal spans
delegate to the original operations. Its first lookup transport failure freezes
the event ring and active spans before original retry clears metadata. Numeric
socket pairs plus QPC windows can correlate client/server attempts; ambiguity,
eviction, dropped spans and missing identities stay visible. If a lookup failure
occurs, the original current group/retry finishes, then no new group is started.
An early stop returns nonzero because twenty groups were not completed.

Only the original `VerifiedJournal._snapshot` is transiently transformed in the
disposable process. Its three `stream.read`, `digest.update`, `os.fsync` calls
receive a delegate-once timing wrapper. The helper asserts exactly one call of
each shape and compares the stripped AST with the original before compilation.
The read loop, chunks, bounds, identity checks, hash/durability comparisons,
exception handling and return remain unchanged. Runtime files are never edited.

Subphase counts/bytes/times and current unfinished operation are bounded in RAM;
per-chunk events never flood the HTTP ring. No journal contents, request bodies,
credentials or exception text are retained. Snapshot reads and hashes are
reported separately; fsync timing here means only the snapshot recovery barrier,
not append/parser/SQLite fsync. Open/fstat/flush/close, scheduling and observer
overhead remain residual. Aggregate phase times overlap; do not add nested
snapshot/reload/lock/HTTP totals or subtract the fake overhead measurement.

Per inner operation the wrapper adds two QPC reads and two recorder lock sections.
The first failure includes separately timestamped subphase state; the two clock
captures are adjacent observations, not an atomic cross-thread instant. No lock
is held across delegated work and no synchronous evidence writer runs inside it.
Patches remain installed through producer cleanup; final evidence is persisted
outside delegated work. The frozen first failure survives later retries/cleanup.

Historical S95 took 5.03 seconds to load 6.93MB history plus20.55 seconds for20
groups. S98 input is17.76MB; rough size scaling suggests about65 seconds plus
instrumentation/cleanup, not a deadline guarantee. The105-second cap remains.
Non-reproduction means only no failure in this short HTTP-only observation;
it neither clears S98 nor justifies a blind35-batch rerun.

`selfcheck-01.json` reports in-memory compilation, AST equality for the actual
method, fake delegation/order/exception checks and a small bounded fake overhead
measurement. It launches no HTTP, engine, Journal or process worker. It is not
a runtime regression suite or a performance calibration.
