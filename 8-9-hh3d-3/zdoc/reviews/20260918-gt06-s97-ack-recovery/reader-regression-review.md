# S97 START/ACK reader regression review

`AUTHORITY=0`; implementation review, not a final critic or acceptance result.
Read-only review; no tests/engine runs performed. The scope is the two fixed-slot
readers in `studio/tests/replay/benchmark_native.gd`, with an eventual null-open
retry that returns to the next normal frame under the existing absolute deadline.

## Existing coverage and the actual gap

- `test_native_benchmark.py` tests project configuration and Python validation
  of synthetic timing/startup receipts. It does not execute either native reader.
- `test_benchmark_readiness.py` validates synthetic startup/root/settling shapes;
  this is separate from START-file availability.
- `test_benchmark_assembly.py` already rejects missing/stale ACK observations,
  late ACK timestamps, wrong START command binding and altered runtime source
  mapping (`test_missing_or_stale_native_ack_observation_rejected`,
  `test_wrong_pid_hash_ack_deadline_and_stale_host_sample_rejected`,
  `test_wrong_start_command_binding_is_rejected`,
  `test_global_clock_baseline_counter_definition_and_start_receipt_rejects`).
  Those regressions should remain; synthetic receipts do not prove FileAccess
  behavior or native state-machine timing.
- `test_benchmark_campaign_stop_completion.py` calls `publish()` when creating
  Stop fixtures, but mocks process ownership. Scoped test search found no direct
  START/ACK publisher regression for close-before-rename, fsync, destination
  refusal or failed exact readback.
- `run_native_benchmark.py` runs native mode `diagnostic`, with
  `diagnostic_immediate`/`diagnostic_none`; its existing small native run bypasses
  both START and ACK readers. It cannot demonstrate the proposed retry.

Current reader deadlines are 600,000,000 us for START and 30,000,000 us for ACK;
the process heartbeat interval is 500,000 us. `_process` calls the heartbeat
before either reader. Both readers check deadline before opening and after
validation; successful ACK also reads fresh counters before its second check.
No repair test should replace these checks with a new timeout, force heartbeats
on every retry, or fabricate a receipt while open remains unavailable.

## Smallest executable native test opportunity

Use the pinned 4.7.2 editor binary and the real accepted adapter/fixture scene.
A diagnostic EditorPlugin subclass can inherit the exact candidate reader,
initialize test offers/barriers from the live root/generation/semantic hash,
and run the inherited `_process` once per ordinary editor frame. Override only
fixture lifecycle/outcome sinks, so cases can inspect whether a receipt or
advance happened; do not duplicate `_wait_host_start`/`_wait_host_ack` in the
test. Fixture outcomes must be labeled reader regressions, not full native
benchmark output. Keep at least one owned native failure/exit integration case
when validating the final repair.

An isolated held Windows handle supplies a repeatable real open conflict and
release signal. The separate rename mechanism probe can establish whether the
pinned FileAccess returns null in that state; it does not by itself prove the
benchmark reader stays pending or advances exactly once. Ordinary malformed,
empty, oversized and wrong-binding inputs can be actual files. A deterministic
short-read needs a narrow test-only fault seam; racing file truncation is not a
reliable regression. Label any seam explicitly and preserve the real reader
branch/validation order. Do not add a broad production IO abstraction solely
to enable the test.

## Minimum matrix, parameterized over START and ACK

| Case | Controlled condition | Required executable result |
|---|---|---|
| R1 normal/read-only overlap | Valid immutable file, including a concurrent read-only holder | One original receipt and one advance; exact digest/identity; no open-recovery event. |
| R2 absent then temporarily unopenable then valid | File initially absent; publish complete bytes under a held conflicting handle; release after multiple observed frames | No receipt/advance while absent or null-open; editor frames and normal heartbeat continue; after release exactly one receipt with actual observed time and unchanged deadline. First error retained and one bounded recovery event; unchanged file bytes. |
| R3 persistent null-open | Hold conflict until the pre-existing absolute fixture deadline passes | Original TIMEOUT, no receipt/advance. Attempt counter increases without resetting issue/deadline or adding per-frame logs/retained objects. A short near-deadline test offer is a synthetic fixture, not a change to production constants. |
| R4 recovered open exposes invalid content | Release the conflict with zero/8193-byte content, malformed JSON, non-dictionary JSON or missing/extra fields | Immediate existing SIZE/JSON/FIELDS failure on that readable frame, with no new grace period or retry of the invalid bytes. |
| R5 readable but stale/wrong binding | Wrong run, batch/deadline, source/profile, ready/native batch digest; source or scene drift | Corresponding existing BINDING/POSITION/HASH/CHANGED/POSTCONDITION failure; no receipt/advance. Test representative wrong hash for both readers; keep the existing broader assembly negatives. |
| R6 short read after successful open | Explicit fault-injected short buffer versus requested length | Immediate distinct short-read failure; never treat it as pending open. Retain actual requested/read lengths and read error before closing. No repaired length, second read or fabricated receipt. |
| R7 deadline expires during successful validation | Test-only bounded synchronization at the late validation boundary, without changing the stored deadline | The original second deadline check still rejects; ACK counters/semantic work cannot turn a late observation into success. If this requires an injection seam, label that case rather than claiming an unmodified timing reproduction. |
| R8 sustained pending/owned Stop | Repeated null-open frames followed by the existing owned Stop/cleanup path | Normal frame/heartbeat progress, bounded diagnostic state, no retry-line flood, real owned exit and zero retained handles/processes. Existing Python Stop routing tests supplement this; they do not replace native cleanup evidence. |

R2/R3 also carry the memory/log check: hold the same slot for many frames and
retain only first error/time/frame plus primitive attempt counts. Compare
ObjectDB/resource counts at the same lifecycle point before and after the
pending interval; no per-attempt Node/Resource/RefCounted, callback, retained
FileAccess or growing history array. Ordinary heartbeat lines are expected;
new input-open diagnostics must be bounded per slot and use a prefix outside
the existing `HH_GT06_BENCHMARK_` marker accounting. Do not sample by allocating
new persistent observation objects every frame.

## Small host publisher regressions

Call the existing `run_benchmark_campaign.publish` against temporary files,
with narrowly delegated operation spies, rather than testing a reimplementation:

1. Observe write→flush→fsync→writer close→rename→exact readback; the final path
   is absent at the pre-rename hook and contains exactly the encoded bytes after.
2. Existing destination or existing exclusive `.tmp` is refused; original bytes
   remain unchanged. On Windows, also create the destination in a delegated
   pre-rename hook to prove no-overwrite behavior, not just the initial check.
3. Inject fsync/rename failure and mismatched readback. No successful publication
   timestamp/ACK is returned; retain failed artifacts for inspection. Do not
   weaken durability or use replacement overwrite to make the test pass.

These tests prove publication ordering and refusal. They cannot establish that
every native open succeeds during the rename visibility interval; R2 covers
the actual reader response to a controlled open conflict.

Before any eventual run, freeze candidate source, harness and binary identities;
run serially with existing owned process capture and fresh IDs. Retain actual
target/helper exits and holder-handle cleanup. Source-string presence tests
may check exact fixture overlay reversal but are not the behavioral proof.
No repair choice, source edit, run or acceptance is claimed by this review.
