# S77 — attribute the first measured ObjectDB increase

AUTHORITY=0. GT-06 remains IN_PROGRESS; no acceptance verdict.

Campaign `gt06-s76-campaign-01`, launch 2, run-00-attempt-02 terminated with
`CAMPAIGN_RETAINED_COUNTER_GROWTH` at batch 5 after 650.625 seconds.
There are five warmup captures and one rejected measured capture, no full run PASS.
Baseline batch 4 ObjectDB 71128 became 71130 at the batch 5 ACK.
ResourceCache stayed 6; editor handles fell 560 to 556; both RSS observations
were within the fixed 10% ceiling. The independent failure inventory confirmed that ObjectDB +2 was the sole
threshold breach in that capture; this does not establish later-run behavior.

Scheduler observation 2026-09-18T00:21:54Z: state 3, result 1, no instances.
Host PID 40900 has actual exit 1. Parent cleanup reports owned tree zero,
owner closed, no cleanup error. Native/editor actual exit and retained handle
proof require their own evidence; scheduler/wrapper values cannot substitute.

Runtime stays checkpoint `04b2f4dc`, 49-file closure
`ffa6071a1fb9d324da7cd860fb41b656e99135a3118367873c7399e85e8432fe`;
profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
No launch 3, gate change, source mutation, or borrowed partial PASS.

Three Astra xhigh workers have distinct assignments:

- `s77_failure_preserve`: exact failure/cleanup/source preservation and all
  threshold calculations, owns `failure/`, `preserve_failure.py`, `failure-summary.md`.
- `s77_object_diagnosis`: disposable attribution instrumentation and diagnosis,
  owns `object-diagnosis.md` and diagnostic helpers here. Coordinator alone
  launches native work after verifying cleanup.
- `s77_capture_audit`: independent static boundary/source audit, owns
  `capture-audit.md`. These workers are not final acceptance critics.

The ACK measurement is made before `_advance_batch()`. A later ready-06 marker
does not make the earlier recorded batch-05 count stale. Batch publication
already has the same +2; the ACK's still-referenced closed FileAccess adds a
consistent +1 to every batch, not this cross-batch difference.

Prior S76 retention supplemental evidence showed ObjectDB +2 and later -2,
including +2 at final idle. This motivates attribution of editor/UI/probe and
background activity; it does not establish a retained leak or authorize a waiver.
The probe must preserve the workload and distinguish reachable inventory from
the unenumerated ObjectDB population. Temporary instrumentation does not become
an accepted benchmark source or replace the required joint measurements.

The existing heartbeat was updated to the failed state and prohibits a blind
launch 3. Exact S76 plan history is preserved under `../20260918-plan-history-s76/`.

## Failure preservation verified

`failure/package-manifest.json` SHA256
`3aaec060e3e70a1fb6072ef5dcabc0d977b7167712220d45091c4083e22cd0ae`:
138 exact copies / 8,955,227 bytes, 324 raw hashes, 36 batch references and
49 source files once. All three Jobs zero/closed, host/editor wrapper handles
closed; host actual exit 1, import actual exit 0, editor actual exit missing
with wrapper exit 2. All 30 Stop slots absent. Source/profile/workstation
unchanged. The sole rejected sample threshold is ObjectDB +2; host RSS +7.273%,
native max status gap 656.642 ms. Raw remains authoritative for this failed run.

## Diagnostic attempts

`gt06-s77-object-diagnostic-01` stopped safely at its first census with
`OBJECT_PROBE_BYTE_CAP`: the initial full reachable inventory exceeded the
diagnostic 8 MiB point limit. No object point was published, so it gives no
class attribution. Native actual exit 86, inner Job zero/closed and wrapper
handle closed; outer actual target exit 1, wrapper exit 0, tree verified,
no timeout. Launched helpers remain frozen in `object-owner-01/` and raw
under `studio/.local/reviews/gt06-s77-object-diagnostic-01`.

The helper used for attempt 02 keeps its launched bytes in `object-owner-02/`. It It keeps the initial
inventory count/class summary and thereafter emits complete added/changed/
removed descriptions; initial IDs are explicitly omitted, not claimed present.
The 8 MiB point and 128 MiB total output bounds stay unchanged. No runtime
benchmark source or acceptance threshold was changed. Process bounds remain
540 seconds inner / 600 seconds outer; 6x100 native cycles and 60-second idle
remain supplemental, with no HTTP/acceptance claim.

The helper now rejects missing actual exit receipts, timeout, unverified tree
or nonzero outer wrapper instead of letting SystemExit(None) report zero. It
adopts constructor `cleanup_owner` and preserves cleanup failures separately.
These two review findings did not invalidate attempt 01's independently read
actual failure exits and verified cleanup. Do not infer any future PASS from
shell exit alone. Python AST was checked before attempt 02 launch.


### Attempt 02 interruption and durable dispatch of attempt 03

Attempt 02 was interrupted by a conversation tool-run cancellation, after five
complete native batches and part of batch 5. No terminal result or actual
native/outer exit and Job-close receipts were captured. The exact scoped
process observation in `object-interruption-02.json` found no remaining process;
that absence is not cleanup verification or a completed diagnostic. Keep its
raw and frozen helper bytes, with no PASS claim.

Attempt 03 was dispatched at 2026-09-18T00:48:08Z using the fixed demand-only
Windows task `HHStudio.GT06.gt06-s77-object-diagnostic-03`, via `object_task.ps1`.
The separate scheduled owner survives a normal chat tool interruption. It has
540-second native, 600-second outer and 720-second scheduler limits, with no
automatic restart. `object-launch-03.json` identifies the helper hashes and
instance; query live status before claiming RUNNING. No authoritative runtime
source or gate threshold changed. Initial reachable IDs remain omitted. The
unchanged-signature census interval is 10 seconds because measured traversal
cost was 1.1–1.6 seconds, so diagnostic timing is explicitly perturbed.

Current workers `s77_disk_design_resume`, `s77_analyzer_resume` and
`s77_index_integration_audit` own separate design/analyzer/audit files. They are
not final acceptance critics. `host-retention-review.md` identifies an additional
O(N) retained command/offset index allocation risk (~4.07 MB incremental versus
~1.91 MB observed RSS headroom; byte values in the report are authoritative).
A disk-derived index is being designed; no source change or full campaign retry
is authorized merely by this estimate. Journal checksums, replay, fsync, locks,
exact dedupe and tombstones remain required, including failure after fsync.


### Diagnostic 03 terminal result

The scheduled task `HHStudio.GT06.gt06-s77-object-diagnostic-03` was observed
terminal at 2026-09-18T00:52:29Z with state 3, result 0 and zero instances, then
deleted only after that observation. The raw result binds six 100-cycle batches
and a final 60-second idle point to run `gt06-s77-object-diagnostic-03`; native
PID 54180 and import PID 47568 exited 0, the outer owner exited 0 with wrapper 0,
no timeout, and the owned tree/Job/handles were verified closed. The 39-file
source closure was checked byte-for-byte before release of the runtime freeze;
its closure is `aa58e8ee7fc4f8399766c8d6beca9dfc1bf10b5247ab7f2aba5cb0d40c259b6f`.
The analyzer exit was 0 and its output is `object-analysis-03.json` (SHA256
`5bbd274888537ad8e70db53b25f0003b6943b2fa5a421c3e998a7e2dcb91943f`).

The result is supplemental only. ObjectDB was 71123 through six batches and
rose to 71127 at idle; the reachable inventory explains two added TreeItems,
while 43724 to 43726 objects remain outside the exposed inventory. Resources,
tree nodes, orphan nodes and filesystem scan flags stayed unchanged, and the
observed RichTextLabel remained 101 paragraphs. This does not prove a leak, a
complete ObjectDB census, or a full-campaign PASS.

### S78 derived-index work

`disk-index-design.md` and `index-integration-audit.md` document the bounded
SQLite derived-index design and service failure boundary. A source WIP adds
`host/replay/disk_journal_index.py`, integrates it before replay, and closes it
after HTTP/Stop/worker drain. JSONL checksums, fsync, writer locks, compaction
and tombstones remain authoritative; derived-index commit failure after the
JSONL fsync is reported as `JOURNAL_INDEX_UNAVAILABLE` with outcome unknown and
forces a locked rebuild. Focused tests are 386 existing replay tests, 5 new
disk-index tests and 16 service tests. This is a candidate WIP, not acceptance.
