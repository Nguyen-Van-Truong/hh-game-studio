# S84 compact census candidate

AUTHORITY=0. Diagnostic overlay only. No runtime source, benchmark thresholds,
acceptance gate, plan or original evidence is changed by this folder.

Frozen helper: `object_probe.gd`, SHA256
`20ed7e62658c247265a8165024682efac78ae9c475a810bb6368e8fe9c75dd40`.
Derived from `../20260918-gt06-s82-attribution/object_probe.gd`. The old helper
remains unchanged. Native parsing/execution and external process ownership
belong to the coordinator's separate original/sham/compact cost harness; this
worker does not launch Godot or claim native proof from Python checks.

The old collector constructed and retained a descriptor for every reachable
identity, including ordinary Node paths and TreeItem cell text. This candidate
retains only:

- An ID-to-class dictionary for all reachable identities.
- Full primitive summaries for exact classes `Tree` and `RichTextLabel` (146 in
  the observed S82 baseline; not a fixed expected count).
- A primitive counter signature and scalar scheduling/byte-cap state.

Each new census builds a current identity map, class counts and per-owner
TreeItem totals. It describes every newly appeared ID, including Node paths and
TreeItem owner/text metadata. Those ordinary descriptors are emitted in `added`
and discarded on return; they are not retained into the next census. Baseline
ordinary Node paths and TreeItem text are never collected. Summary descriptors
are compared with their prior summaries for `changed` rows. Removed ordinary
IDs contain ID, class, current `still_valid`, and explicit
`old_metadata_available=false` / `old_metadata_scope=not_retained`.

ID strings retain the signed decimal form produced by Godot. Membership does
not require positive IDs or convert them through floating point. Only the
validity API converts the signed string back to a Godot integer, as in S82.

This still provides complete membership/class reconstruction within the probe's
partial reachable census, class deltas, and actual per-owner TreeItem count
changes. It does not identify the old owner of every removed TreeItem. Changed
ordinary Node properties and baseline child text are outside coverage; current
snapshots explicitly label that limitation. A changed Tree summary does not mean
its unchanged-ID children have unchanged content.

The callable interfaces remain `_object_probe_sample(label, force=false)` and
the S82 split marker before `_object_probe_after_batch()`. The new
`_object_probe_clear_retained()` clears both retained maps and the signature for
the A/B release phase. It prohibits further sampling in the same output series
instead of resetting sequence and risking a silent rebase/overwrite. No
Object/RefCounted references are intentionally retained by these structures.

Snapshot cap 512, individual byte cap 8 MiB, cumulative cap 128 MiB, no-overwrite
publication, flush/rename, and SHA256 readback are preserved. Primitive retained
state advances only after verified publication. Counter drift during collection
and post-publication ObjectDB drift fail the disposable run. `FileAccess` is
closed and its local reference cleared before the latter in-function check.
The caller's post-return/ACK counter checks should remain in place as well.

Memory/time improvements are hypotheses until the owned A/B run supplies actual
external RSS, handles, timing, counters and exits. Clearing GDScript containers
does not guarantee that allocator pages immediately leave RSS. Godot's static
memory value is supplemental and must never replace the RSS gate.

`check_compact_snapshots.py` is a small read-only consumer for the compact
membership/count contract. Pass published snapshot files in sequence order:

```powershell
python -B check_compact_snapshots.py <object-0000.json> <object-0001.json>
```

It checks signed IDs, membership/class/count arithmetic, owner totals, scope and
counter equality, and emits deltas with residual/unattributed growth. It hashes
only those input bytes; it does not verify process cleanup, publication/ACK
receipts or a campaign. Its output explicitly says `godot_execution_verified`
and `publication_receipts_verified` are false. `test_compact_contract.py` uses
synthetic JSON only; it is not a model of Godot memory usage.

Common S82 fields are preserved, with additive `collector_variant` and coverage
fields. The S83 analyzer is fixed to the old run/source and assumes old removed
descriptors are retained, so it must not be used unmodified as a validator for a
new compact run. In particular, an ordinary object emitted when newly added may
later be removed with unavailable prior metadata; that is deliberate.

Static checks do not establish GDScript parse success. The focused Python tests
must run only after the coordinator's native measurement lane is terminal.

After the coordinator reported its compact arm terminal, seven focused Python
contract tests passed with actual exit 0 (`tests-01-run.json`). The checker also
validated the real `gt06-s84-cost-compact-01` `object-0000.json`, actual exit 0:
ObjectDB 71,047, reachable identities 27,402, residual 43,645. The exact input is
bound in `compact-baseline-01.stdout.json` and the invocation/exit/hash receipt
is `compact-baseline-01-run.json`. That is one baseline census, not proof of a
second-growth census or the full HTTP/native sequence. The helper remains at the
frozen hash above; no engine was launched by this worker.

The coordinator then supplied a terminal controlled-growth run,
`gt06-s84-cost-compact-growth-01`. The same checker passed its three real
snapshots with actual exit 0 (`compact-growth-01-run.json`). The separate
`compact-growth-01-semantic-check.json` verifies the new Tree named
`DiagnosticCensusTree`, its item text `diagnostic-added-item`, matching removed
IDs/classes with `still_valid=false`, and that Tree's item counts 0 → 1 → 0.
All 15 newly reachable identities are removed in the third snapshot; reachable
counts are 27,402 → 27,417 → 27,402. Retained summaries are 146 → 147 → 146 and
descriptors collected per census are 146 → 161 → 146.

ObjectDB counts are 71,047 → 71,082 → 71,057; the residual is 43,645 → 43,665 →
43,655. The reachable set returning to baseline therefore does not mean the
whole ObjectDB count returned to baseline. This proves the compact publication
can expose controlled additions and removals; it is not natural leak
reproduction, attribution of the residual, or full-sequence acceptance. Native
process/cleanup proof remains in the coordinator's separately owned harness.
