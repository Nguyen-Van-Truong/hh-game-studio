# S102 decision and coordinator validation

AUTHORITY=0. Not an acceptance-critic verdict. GT06 remains IN_PROGRESS.

## Why a new formal candidate

S100 short probes did not reproduce the previous 2 s lookup or 20 s import
failure. HTTP200 maxgap446.3703ms/lookup382.548ms and coldimport5.235s completed
with actual exits0 and clean Jobs/handles. Snapshot hashing took70.5075% of
snapshot time in the copied-history probe, but this does not explain a tail.
The warm-cache hash read change saved only2.3ms; journal source stays unchanged.
See S100 short-probes-inventory.json for distinct raw/portable hash domains.

The selected repair is to retain bounded attribution **inside the formal run**,
so a future failure need not be chased by another unrelated long diagnostic.
This fixes an evidence gap, not a demonstrated latency/root cause. No acceptance
exception is added; overhead remains inside time/RSS. Old diagnostic and failed
prefixes remain excluded from F13/F14. New source requires a fresh campaign.

## Source and checks

Formal source53 closure:
`7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`.
Original profile:
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

Added only benchmark_http_phases.py and benchmark_import_observer.py;
changed benchmark_commands.py, benchmark_transport.py and run_benchmark_campaign.py.
Core transport, verified journal, native GDScript and workload gates are unchanged.
The import observer closes before host/editor startup and memory baseline.
HTTP initialization precedes producer startup; 8192 events/64 active spans and
first lookup-failure window remain bounded. Original command schema stays1.3.0.

- Unit-01:130/130 affected tests, actual PythonPID26092 exit0,13.032s, exact
  source/test hashes unchanged. Includes real small HTTP fixtures, observer ABI,
  malformed sidecars, cleanup failures, Stop races and task routing.
- Owned preflight run-01:10.656s overall, native importPID30408 exit0,
  native helper exit0; hostPID24852/helper23568 exits0. Both Jobs zero/closed,
  process/probe handles released, threads/listeners/index closed, no stderr.
  Original import limit20s; elapsed5.016s;52 samples. Two groups20commands,
  effects2→4, maxgaps41.9596/54.4386ms. HTTP no dropped/evicted/open spans,
  missing identity or transport failures. Source/helper/binary pins unchanged.
  Parent revalidated sidecars against actual host/import exits. No native
  benchmark cycles and no memory/latency acceptance claim.

## Independent implementation review findings

Import worker found two concrete integration gaps: internally captured observer
errors could bypass the early check, and retry-close state was absent from the
terminal record. Root fixed both: raw snapshot is persisted then validated
before producer creation; compact post-retry observer state is retained, while
the initiating error/cause and all cleanup errors survive. Tests exercise these.

Separate read-only HTTP review found constructor active-capacity allowed256
while validator allowed64. Constructor now matches64; boundary regression added.
No other concrete semantics/cleanup issue was reported. These are implementation
reviews, **not** the two final acceptance critics.

## Continuation and lessons

Next fresh campaign gt06-s102-campaign-01 retains the original ten pairs×35batch,
5warmup+30measured and1000HTTP+100native. Do not edit frozen source during it.
On failure inspect raw sidecars and actual lifecycle evidence before retry.
On success verify full dataset and dependency-bound functional lanes, then two
new independent final critics on one frozen closure. GT07–10 remain gated;
GT08 physicalAndroid. No reliable whole-plan ETA exists.

Raw bytes use scoped `* -text`; explicit add--renormalize plus staged-blob check
prevents Git normalization from changing retained evidence. S100 correction is
845ea3fe. Check subprocess exit before commit, since PowerShell can continue
after an earlier command failure. Assign documentation filenames explicitly too:
the helper README overlapped an initial coordinator draft; final decisions are
consolidated here, with no runtime or frozen execution-file overwrite.
