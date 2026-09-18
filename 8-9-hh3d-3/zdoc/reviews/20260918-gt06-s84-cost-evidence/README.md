# S84 census allocation cost — four preserved diagnostic arms

AUTHORITY=0. FORMAL_ACCEPTANCE=false. These are four short, serial native
allocation experiments, one trial per arm. They are not the HTTP/native full
sequence, an official benchmark dataset, a leak fix, or an acceptance verdict.
Each native arm completed one semantic cycle and exited 0 with a natural clean
tree. The **original Python collector still exited 1**; that failure is retained.

## Observed memory

RSS is sampled by the external host before each phase ACK. Godot static
allocator bytes are supplemental. Values below are raw bytes; changes are
relative to that arm's own `before` observation, without sham subtraction.

| Arm | Before RSS | Retained RSS change | Released RSS change | Retained static change | Released static change |
|---|---:|---:|---:|---:|---:|
| original | 749,113,344 | +117,919,744 | +117,919,744 | +103,247,732 | +31,554,424 |
| sham | 748,994,560 | -221,184 | -638,976 | +10,952 | +20,520 |
| compact | 747,802,624 | +2,412,544 | +2,412,544 | +5,255,684 | +802,364 |
| compact-growth | 750,911,488 | +3,297,280 | +7,245,824 | +5,255,740 | +819,884 |

The compact-growth arm has a fourth `growth` phase between retained/released:
RSS 757,690,368, **+6,778,880 bytes** over before; static change +5,405,764.
All 13 observations, monotonic sample times, native receipt hashes and exact
deltas are in `derived-facts.json`; full records remain in the copied raw arms.

These single trials support the narrower observation that the compact census
retained substantially less memory here than the original census. They do not
prove causation for the prior full-sequence RSS failure or no leakage. RSS can
remain elevated after collector state is cleared even when static memory falls.
No timing/RSS acceptance threshold was changed or inferred from these trials.

## Census coverage and object drift

Full raw census JSON is copied: original 1, compact 1, compact-growth 3; sham
has no census by design. They are **partial reachable inventories**, not full
ObjectDB censuses. Original baseline covers 27,401 IDs in 820,954 microseconds;
compact covers 27,402 in 521,009 microseconds. Compact-growth covers
27,402 → 27,417 → 27,402 IDs (baseline/growth/restore), with 15 additions then
15 removals and one summary change in each later census. The growth helper
creates and frees a diagnostic Tree/TreeItem; this is controlled diagnostic
coverage, not attribution of an organic game/editor leak.

The compact records retain zero ordinary descriptors and 146/147/146 special
summaries in the growth arm. Content changes cover exact Tree/RichTextLabel
summaries only; prior ordinary-object removal metadata is explicitly unknown.
All five raw census records report equal counters immediately before/after
their synchronous collection. **Counts between phase waits are not equal**:
original 71046→71050→71055, sham 71047→71051→71055, compact
71047→71051→71055, growth 71047→71051→71086→71061. These phase changes
must not be silently converted into a count-stability or no-leak claim.

## Original collector failure and source domains

The original executed `measure_cost.py` asserted that ObjectDB counts stayed
equal across all phase observations. The assertion fired after native
completion, before `c.verify_sources(source)` and the final helper-after checks.
Its `failure.json`, traceback, all native outputs and exact executed helper are
preserved. Its missing `result.json` stays missing. The derived outcome is
**NATIVE_ALLOCATION_EXPERIMENT_COMPLETED_WITH_COLLECTOR_FAILURE**, not PASS;
Python collector PID43228 actual exit **1** is never rewritten.

`offline-source-check.json` supplements those skipped checks at its own recorded
timestamp. All **51 current runtime files** match all **204 frozen copies**
across the four arms, with base closure:

`e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`.

All **12 executed helper bindings** match each arm's declared hashes,
`raw/source` bytes and preserved packet copies. This does not retroactively
claim that the skipped checks ran during the original experiment. The shared
profile remains `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

| Executed `measure_cost.py` | SHA-256 |
|---|---|
| original | `193719fae8ab03ed44a5081195399cbbdeb7243854f0641abdc7b5d00acec14f` |
| sham, compact | `835bb732dcefb697b2847238c250068c98a326ecde9ef888d7e4e7dfc810f69f` |
| compact-growth | `30ae92b366f345a4f40f2653f67012af983ab405ee20b5540eed15db50b5a9c8` |

Current helper snapshots are retained separately under `current-context/`.
`current-helper-comparison.json` reports mismatches; current source never
replaces an older executed helper. Each effective native overlay is copied and
bound by the initial/runtime/invocation maps. The outer bootstrap runner
snapshot matches all four invocation-declared runner hashes. Binary hashes
are retained from invocations, not rehashed here.

## Actual exits and cleanup

| Arm | Python collector target / actual exit | Outer runner helper / exit | Godot editor / actual exit | Godot import / actual exit |
|---|---|---|---|---|
| original | 43228 / **1** | 40816 / 0 | 18412 / 0 | 23448 / 0 |
| sham | 43496 / 0 | 39204 / 0 | 48524 / 0 | 7944 / 0 |
| compact | 43920 / 0 | 5544 / 0 | 21472 / 0 | 40276 / 0 |
| compact-growth | 17748 / 0 | 45692 / 0 | 30884 / 0 | 41176 / 0 |

All eight Godot target exits have actual `process-exit.json` receipts. Editor
and import captures separately record their own native helper wrapper exit 0,
natural tree exit and Job zero/closed, but **do not identify those native
helper PIDs**. Those are different helpers from the outer runner PIDs above.
Editor wrapper-handle close receipts are present; import wrapper-handle
receipts are absent. These documentation gaps are retained, not inferred away.
All outer capture trees are verified and not timed out. Cleanup records have
no reported errors, no retained probe handle and a closed owner. No process
absence observation or cleanup operation was needed for this packet.

## Preservation and recheck

`raw-inventory.json` inventories **576 original files** across eight raw/outer
roots: **420 exact hashes (6,349,507 bytes)** and **156 cache/settings metadata-only
exclusions**. The first pass ended at 10:06:45Z, before the later long compact
diagnostic began. Cache contents, including `.godot`, are not read or copied.
`copy-map.json` binds **216 exact copies (3,437,707 bytes)**; 51 frozen runtime
files per arm remain fully hashed in place. Six small current-context files
are distinct snapshots. Selected evidence passed a limited credential-pattern
and sensitive-key screen; this is not universal secret-absence proof.

Before any selected copy was written, the collector verified the existing
inventory, all source/helper maps, invocations, receipts and observations. It
uses exclusive creation and then verifies copy bytes and unchanged original
file sets/hashes/size/mtime. No raw files or earlier packets were changed.
`.gitattributes` preserves exact bytes in any later staging.

The collector exited 0; the additional offline source checker exited 0.
The packet sealer checks the selected copies and current-context snapshots,
then hashes packet files only. Once the active long diagnostic has finished,
a complete read-only original/copy/static recheck can be run from `8-9-hh3d-3`:

```powershell
python -B 'zdoc/reviews/20260918-gt06-s84-cost-evidence/preserve.py' verify
python -B 'zdoc/reviews/20260918-gt06-s84-cost-evidence/offline_source_check.py' verify
```

The second command deliberately rechecks current runtime source and will fail
if it has changed since this observation. Neither checker imports runtime
modules or executes engines/tests. Full raw verification needs the excluded
from-copy frozen sources to remain at their original paths. Cache content is
outside the hash guarantee. Same-agent verification is not an independent critic.

The package digest hashes exact `package-manifest.json` bytes; that manifest
enumerates every packet file except itself and `package-manifest.sha256`.
It is a preservation seal, not acceptance. No runtime/plan changes, tests,
engine launch, old packet edit or commit were performed in this lane.
