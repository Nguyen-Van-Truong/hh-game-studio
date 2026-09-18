# S91 status-gap failure analysis

AUTHORITY=0. Read-only analysis of preserved S91 raw evidence, 2026-09-18.
Diagnostic only; no acceptance, repaired-runtime or root-cause verdict.

Raw root: `studio/.local/reviews/gt06-s91-sparse-attribution-01/`.
The 17th completed capture/joint pair was written at 14:25:58Z. The child
failed screening at batch 16 / `joint_observation` with
`child-failure.json.code=CAMPAIGN_STATUS_GAP`; `completed_batches=17` and
`completed=false`. Earlier alive observations do not supersede this terminal
failure. Root coordinator owns terminal exit/cleanup verification and sealing.

## Exact failed metric and provenance

`command-16.json.max_status_gap_ms=2072.4595` exceeds the unchanged 2000 ms
screening limit by 72.4595 ms. Its `status_gap_scope` is
`host command-lane response progress; not editor UI heartbeat`.
`sample-preview-16.json.max_status_gap_ms` contains the same value.
`project/benchmark/out/batch-16.json.max_status_gap_ms=601.142`, its
`start_permit.max_status_gap_ms=537.149`, and
`joint-16.json.barrier_receipt.max_status_gap_ms=601.142`.

The host maximum is the first response interval:
`host_response_mono_us[0]=639608563267` to `[1]=639610635726`.
The integer microsecond projection gives 2072.459 ms; the persisted
2072.4595 ms is computed from original nanosecond timestamps.
The second largest projected gap is 919.391 ms. The first command is
`commands[0]`, `gt06-s91-sparse-attribution-01.b16.inspect.0`:

- `started_mono_us=639609778148`: 1214.881 ms after batch start.
- `receipt_mono_us=639610635726`, `receipt_ms=857.5781`,
  `receipt_status=ACCEPTED_PENDING`, `receipt_code=QUEUED`.
- `terminal_mono_us=639611042455`, `terminal_ms=1264.3071`,
  `terminal_status=COMMITTED`.
- `memory_before.monotonic_us=639609778071`, only 77 microseconds before
  that first submit timestamp; this does not split preceding setup stages.

The batch has `status=COMPLETE`, 1000 commands, effects 3200 to 3400,
and all 200 `effects_per_admission` entries equal 1. Its failure was assessed
after command and native work completed, not at an admission rejection.
Joint ACK objects remain 71128, resources 6; editor handles 555 and RSS
118452224 bytes. This failure does not establish ObjectDB growth.

## Nearby completed batches

Values below come from `command-NN.json` and
`project/benchmark/out/batch-NN.json`; setup is first command start minus
command-batch start. Times are milliseconds.

| Batch | Host maximum gap | Before first submit | First submit response | Native maximum gap |
|---|---:|---:|---:|---:|
| 11 | 439.5057 | 38.501 | 58.2701 | 564.459 |
| 12 | 1422.8111 | 65.286 | 116.3219 | 641.720 |
| 13 | 1535.1258 | 891.692 | 643.4334 | 773.454 |
| 14 | 1329.3451 | 663.367 | 665.9780 | 611.200 |
| 15 | 1226.5087 | 514.930 | 711.5788 | 578.386 |
| 16 | 2072.4595 | 1214.881 | 857.5781 | 601.142 |

Batches 13 through 16 have their maximum in the first interval. Batch 12's
maximum occurs later, between response entries 245 and 246. Consequently,
the observed slowdown is not proven to involve only connection setup.
All six batches retain COMPLETE command reports and unit admission effects.

## Frozen-source interpretation and limits

The preserved `source/studio/tests/replay/benchmark_commands.py` starts the
status clock before `_connect_batch()` and memory sampling. `_connect_batch`
rotates/issues a credential, creates the client, calls discovery, and obtains
a lease. Discovery and lease responses are not recorded through `_received()`
in this frozen implementation. The first recorded response is the first
command admission receipt. Thus the failed aggregate interval spans both
setup and a command response. Neither of the two coarse components alone
exceeded 2000 ms in batch 16.

`source/studio/tests/replay/benchmark_assembly.py` assembles the maximum of
command, start-permit and ACK gap values. `run_benchmark_campaign.py` screens
measured samples against 2000 ms. This is the actual unchanged metric; this
analysis does not retrospectively alter S91 or treat a newly segmented value
as acceptance evidence.

Raw data do not split the 1214.881 ms into credential rotation, discovery,
lease, memory sampling, request creation or scheduling. They cannot establish
CPU/disk contention, journal cost, a leak, or sparse-probe causation. Native
cycles start after the host command batch. Only the baseline sparse snapshot
at batch 4 was observed; no first-growth snapshot was produced. The root
cause of the host slowdown remains unproven.

## Lowest-cost next probe

Use a bounded host-only diagnostic with monotonic spans around credential
rotation, discovery, lease, memory sampling, request creation, and first
submit/admission. Preserve accumulated-history conditions where practical;
a clean-history-only pass cannot resolve the late-batch slowdown. Bind every
reported response timestamp to its actual setup/command/cancel/lookup event,
and reject invented extra samples. Preserve the original 2000 ms screening
threshold and retain any individual setup segment exceeding it.

Any instrumentation or schema correction requires its own source closure,
verification and measured proof. It is not a demonstrated performance fix,
and this report author has run no engines or tests and changed no legacy raw.
