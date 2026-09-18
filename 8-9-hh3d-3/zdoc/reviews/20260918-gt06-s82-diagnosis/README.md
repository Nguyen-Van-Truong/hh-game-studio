# S82 ObjectDB diagnosis — corrected analysis of existing raw

`AUTHORITY=0`; diagnostic only. The six native batches completed 100 cycles
each, followed by at least 120 seconds of idle sampling. All 25 snapshots and
six batch counters report ObjectDB **71,129** and ResourceCache **6**. The
native editor elapsed time is **299.343 seconds**.

Stable counts do not mean stable identities. At each of the five settle
snapshots between batches, the reachable inventory records **18 additions and
18 removals: 17 TreeItems and one Node3D in each direction**. There are no
added/removed identities at after-batch or idle snapshots. The first snapshot
contains 146 selected initial Tree/RichTextLabel descriptors; these initialize
the inventory and are not evidence of runtime growth. The inventory covers
27,401 reachable objects, leaving 43,728 ObjectDB objects unattributed. It is
not a full ObjectDB census, and samples do not establish behavior between them.

Independent raw checks match editor PID 39992 exit 0, import PID 26028 exit 0,
outer Python child PID 38336 exit 0, and outer wrapper PID 6720 exit 0. The
native Job is zero/closed with no retained Job handle; the editor owner reports
its wrapper process handle closed. Native stdout/stderr contain no diagnostic
warning/error. Process receipts, source maps, native index, completion marker,
batch files, and snapshot identities are cross-checked by
`analyze_existing_raw.py`; an exit banner alone is not the proof.

This narrower no-HTTP probe **did not reproduce the S81 +2**. It does not
identify that owner or rule out a leak. The now-completed long probe similarly
has stable sampled counts but takes about 507 seconds, much shorter than the
roughly 31-minute failed S81 campaign and without its host-command sequence.
Neither diagnostic authorizes a full-campaign retry or changes a threshold,
counter, profile, runtime source, acceptance criterion, or GT-06 status.

`analysis-result.json` separates count stability from identity churn.
`diagnostic-corrected.json` is derived metadata with its raw provenance.
The original `diagnostic-01.json`, `result-01.json`, executed helpers and outer
receipts remain unchanged. Previous derived descriptions are preserved in
`superseded-derived/`; their no-churn claims are superseded by this report.
The complete raw tree remains at
`studio/.local/reviews/gt06-s82-object-diagnostic-01`.

The frozen probe source closure is **40 files**,
`ebed9418490379bb902d2049e4a2f98a96e3378d09b369aef02684e16214c74e`,
with 55 source/runtime map entries after adding the disposable project. It is
distinct from the S81 campaign's 51-file closure. Exact-byte verification binds
the frozen copies, immutable project files and final mutable scene to the
native records; it does not transfer full-campaign evidence to this probe.

`artifact-hashes.json` covers every local raw file and every review file except
the manifest itself. Its domain is exact filesystem bytes, **not Git-normalized
bytes**. The executed Python helper contains a CRLF and Git's clean filter
changes its blob hash. `git_byte_audit` records both IDs. Do not rewrite the
helper to silence whitespace or claim that ordinary Git staging preserves the
executed bytes. No Git attribute change is made by this repair.

Reproduce the analysis without any engine or helper launch, from repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s82-diagnosis/analyze_existing_raw.py --verify
```
