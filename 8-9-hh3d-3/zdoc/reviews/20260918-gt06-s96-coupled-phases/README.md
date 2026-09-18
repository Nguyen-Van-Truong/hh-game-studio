# S96 coupled phase diagnostic — prepared, not executed

AUTHORITY=0. No formal benchmark PASS, root-cause claim or final critic verdict.
The fixed new run is `gt06-s96-coupled-phases-01`; import preflight is
`gt06-s96-coupled-phases-preflight-01`. Any later source/helper edit after freeze
needs fresh identities and evidence; never overwrite an old run or launch slot.

`coupled_phases.py` composes the immutable S93 diagnostic supervisor and external
observer rather than copying them. The original helpers remain at their original
paths in the new helper map and are copied as exact source evidence. Rebinding
their `__file__` only selects this new child entry. S93/S95 evidence is unchanged.
The retained supervisor uses the original campaign child and cleanup validator;
the outer gated target becomes the supervisor in the same PID, with the checked
seven-slot Job and 7530s watchdog. Inner 7410s host limits stay unchanged.

The formal base is exactly 51 files / closure
`564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752`.
Profile remains
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
This runs one original full-mode sequence of 35 batches, 1000 HTTP commands and
100 native cycles per batch, retaining warmup, ready/start/joint/ACK sequencing,
deadlines, status/latency/counter gates and Stop semantics. It is instrumented
diagnostic evidence and cannot enter the ten-run formal dataset.

## Two bounded observations

- HTTP: install the separately pinned `http-phases/phase_observer.py` factories
  only inside the disposable owned child. They delegate unchanged Journal,
  benchmark Host/Client and HTTPConnection methods. The recorder holds a
  512-event ring, at most 64 unfinished spans and the first lookup transport
  failure snapshot before retry; fixed-route totals retain other failures.
  `http-phases-final.json` is written once,
  after original `run_child` cleanup. No wrapper disk IO, request bodies,
  credentials or exception text. Nested spans overlap; server dispatch→lookup
  is not a pure lock-wait measurement. Overflow/eviction/missing identity remain
  explicit. A hard kill can prevent the final write: absence is GAP, never
  evidence that no failure occurred. Instrumentation overhead is not subtracted.
- Native: the S95 primitive Tree/TreeItem/Node3D collector is adapted in the
  copied project to run **after ACK validation, inspection and ACK file-hash
  readback, immediately before fresh ACK object/resource counters**. It records
  baseline at ACK batch 4 and first later growth, with cap 32768 primitive IDs
  and at most two snapshots. Original `_write_batch` bytes, ACK `observed` time,
  deadline check and heartbeat remain unchanged. No added heartbeat or adjusted
  barrier deadline. S96 schema/phase/trigger labels distinguish this lifecycle
  from S95's prepublication census. Primitive collection/diff code is unchanged;
  the adapted function receives only the already validated ACK digest.

Sparse `sparse-00/01.json` and `sparse-post-00/01.json` must bind their run/PID,
batch, ACK digest, object/resource counts and process frame to the corresponding
original ACK receipt in `joint-NN.json`/native index. Their collection/publication
times precede the original `ack_observed_mono_us`; counter self-drift, missing
growth capture or mismatched lifecycle is a diagnostic GAP. An incomplete run
may have no baseline/ACK receipt. Do not match these rows to earlier native
batch memory or reinterpret the inventory as complete ObjectDB enumeration.

## Root validation and dispatch sequence

No command in this section was executed while preparing these files.

1. Run the six bounded static checks in `test_coupled_phases.py` through the
   owned unit lane. They exercise exact native-byte reversal, unchanged
   `_write_batch` and ACK tail, new lifecycle labels, fail-closed anchors and
   sanitized diagnostics. Pair with the recorder worker's retained focused
   tests and real HTTP compatibility smoke; those are separate scopes.
2. Run `python -B <this-directory>/coupled_phases.py --describe` to obtain the
   actual request/helper digest. `register_task.ps1 -Command register
   -HelperSha256 <request.helper_sha256> -PythonExe <pinned-python.exe>` creates
   a demand-only current-user task and exact request/XML, without dispatch.
   Every external imported helper, the original S95 probe and the source-map
   reference is pinned; all launch modes compare exact current pins to request.
3. Run `python -B <this-directory>/coupled_phases.py --preflight` under root's
   serialized owned lane. This imports the copied project without activation;
   it cannot test the ACK hook. The first full batches of the subsequent
   diagnostic must validate the real ACK chain; root checks the first ACK and
   baseline batch 4 through bounded progress reads. Preserve any failure.
   This package provides no shortened coupled run or bypass of full-mode work.
4. After these checks, `register_task.ps1 -Command start` checks preflight,
   current pins, fresh output, exact XML and all visible/hidden `HHStudio.GT06.*`
   tasks, then claims its one-use dispatch slot before the COM call. There are
   no triggers or automatic retries. `status` reports scheduler state only;
   `delete` is allowed only with no task instances and terminal task state.

Stop uses the unchanged `HH-GT06-CAMPAIGN-STOP-1` record at the new raw run's
`stop-request.json`, bound to its run ID, source digest and
`context.json#/campaign_sha256`. Publish through the existing exclusive
temp/no-overwrite rename path. Presence/invalidity remains fail-closed; no
process-name kill, source edit, ACK fabrication or timeout extension is added.

## Terminal evidence and limits

Require original child-terminal cleanup, distinct target/helper actual exits,
Jobs zero/closed and released retained handles. `supervisor-return.json` and
observer terminal keep their own-exit-unobserved fields; root must join external
scheduler terminal/no-instance proof, never infer an actual exit from a return
value. Forced exit is not natural success. The phase snapshot does not prove
cleanup. Complete the final source/helper readback and exact raw seal after all
owned processes stop; preserve missing receipts and failed prefixes.

The inherited S93 manifest covers emitted JSON/log/native JSON. The effective
native text is additionally saved as `effective-benchmark-native.gd`, whose hash
is in `native-overlay.json`; include that exact file and the excluded raw
locators in root's terminal seal. No final acceptance signature is reused.
