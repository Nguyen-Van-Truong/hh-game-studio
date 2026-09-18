# S95 terminal selected-object analysis

AUTHORITY=0. This is an offline diagnostic analyzer, not an acceptance verifier.
It does not launch processes, import studio runtime, read stdout, modify raw
evidence, enumerate processes, or sweep the source tree. No test or execution
was performed by its author while the native diagnostic was active.

The only input run is `gt06-s95-native-isolation-01` and its fixed `-outer`
sibling under `8-9-hh3d-3/studio/.local/reviews/`. Do not use this analyzer for a
different source, helper version, run, or smoke workload. The fixed native
source and helper pins are the launch pins; it checks their manifest/map
bindings and the two archived helper files plus effective overlay. It does
not rehash the entire archived source closure. S83's strict Reader, duplicate
JSON-key checks, hashing and closure helpers are reused under an exact source
pin. The identity reconstruction follows the S84 compact checker approach,
adapted to the smaller S95 schema without importing its runtime verifier.

After the coordinator confirms all writers have stopped and preserves the
outer observer's actual Task Scheduler exit, run from the repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s95-result-prep/object-analysis/analyze_native.py --writers-stopped
```

JSON is emitted to stdout. The flag is an operator assertion, not independent
process proof. Both `output-manifest.json` and the outer `terminal.json` must
exist; missing or invalid input returns `ANALYSIS_GAP` and exit 2. A structurally
valid failed/incomplete terminal run may retain an observed prefix and growth,
but returns exit 2 and cannot support an absence conclusion. Exit 0 means the
offline arithmetic completed with completed-diagnostic receipts. It never
means the formal benchmark passed. Process exits/Jobs/handles are copied from
the actual saved receipts; this analyzer does not reverify OS ownership or
invent an actual exit for the outer observer.

The analyzer reads only named JSON/source artifacts. It checks each used raw
JSON file against the native output manifest, complete index batch hashes,
run/PID/dimensions, baseline batch 4 and first later count-growth selection.
Sparse publication SHA, counter equality, synchronous process frame and
collection/publication timestamps must bind the same native batch readback.
These are prepublication native observations, not the coupled post-ACK phase.
The native `warmup=false` field remains unchanged; batch 4 is an analytical
baseline for this diagnostic, not a formal measured sample.

The primitive inventory covers reachable Tree owners, their TreeItems and
the reachable Node3D family only. It keeps signed int64 IDs exact, rejects
floating-point IDs, and emits identity strings to avoid downstream JavaScript
rounding. Baseline membership, delta subsets, unique ownership, class/family
counts, owner additions/removals and TreeItem owner moves must reconcile.
The growth inventory is reconstructed from baseline plus emitted deltas;
S95 does not publish an independent second complete ID list. Concrete Node3D
subclasses, content and allocation stacks are not captured. Runtime validity
flags are observations, not independent destruction or leak proofs.

Only baseline and first growth are sampled. If no growth snapshot exists,
later identity stability was not measured. Count stability can coexist with
identity replacement. An ObjectDB count increase can differ from the selected
ID net increase; their difference is an unattributed net count, not a list of
identified leaked objects. All baseline IDs are initial inventory, never
reported as added growth.

A completed negative result means **not reproduced in this isolated workload**.
It cannot rule out a leak or resolve S93/the formal benchmark. This workload
omits HTTP producers, host-start/ACK work and their load/idle durations, and
has at most two partial identity samples. Wall time and the unchanged native
heartbeat result remain visible. No RAM, count, handle or latency threshold
is changed or relaxed by this analysis.
