# S82 long native diagnosis — corrected analysis of existing raw

`AUTHORITY=0`; no GT-06 or full-campaign acceptance. Native index, batch files,
their hashes and the COMPLETE record agree on **16 batches × 100 cycles**.
There are **45 snapshots**, with ObjectDB **71,127** and ResourceCache **6**
at every sample and batch counter. Native editor elapsed time is **506.985
seconds**, including at least 120 seconds after the final batch. This is much
shorter than the roughly 31-minute failed S81 campaign; 16 native batches do
not reproduce 16 full campaign batches or their HTTP host-command sequence.

The reachable inventory records **18 additions and 18 removals** at each of
15 between-batch settle snapshots: 17 TreeItems and one Node3D per direction.
After-batch and idle snapshots have no additions/removals. The 146 selected
descriptors in the first snapshot initialize the inventory and are excluded
from churn. The inventory covers 27,401 reachable objects; 43,726 ObjectDB
objects remain unattributed. Stable sampled counts do not prove unchanged
identities, stability between samples, or absence of leaks.

Native editor **PID 11332 exited 0**, import **PID 43304 exited 0**. Their
process-exit receipts agree with captures; native logs have no warning/error
and empty stderr. The native Job reached zero/closed, and the editor owner
reports its wrapper process handle closed. The separate **outer Python child
PID 49872 exited 1**; **outer wrapper PID 45692 exited 0**. Wrapper exit 0
does not turn the Python helper into a success.

The executed Python helper failed at `assert len(batches) == 6` after native
completion. Its original traceback, `failure.json`, copied/executed helper
bytes, and raw `diagnostic.json` with stale `native_batches: 6` remain
unchanged. There is no raw helper `result.json`. The corrected value 16 lives
only in `diagnostic-corrected.json` and `long-result.json`, with provenance to
the original raw metadata. The previous derived report is preserved in
`superseded-derived/`; its no-churn and leak-rule-out statements are withdrawn.

`long-result.json` now separates `all_object_count_deltas_zero: true` from
`all_identity_deltas_zero_after_initial_inventory: false`, and distinguishes
native completion, child exit and wrapper exit. **This no-HTTP probe did not
reproduce the +2; it does not rule out a leak or identify the S81 owner.** No
runtime source, profile, threshold, acceptance criterion or plan status was
changed, and no campaign retry is authorized by this report.

The frozen probe source closure is 40 files
`ebed9418490379bb902d2049e4a2f98a96e3378d09b369aef02684e16214c74e`,
with 55 source/runtime entries including its disposable project. It is
distinct from the S81 campaign's 51-file closure. The raw tree is retained at
`studio/.local/reviews/gt06-s82-object-diagnostic-long-01`.

`artifact-hashes.json` covers all raw and review files except itself using
exact filesystem bytes. The executed helper contains two CRLFs; Git's clean
filter changes its blob hash. The `git_byte_audit` field records both hashes.
No helper was normalized or edited, and no Git attributes were changed.
This package must not be represented as byte-exact in Git until a separate
index/blob verification actually proves that property.

Reproduce both diagnostic checks without starting an engine or helper:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s82-diagnosis/analyze_existing_raw.py --verify
```
