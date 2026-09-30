# GT06 diagnostic lane

This lane records diagnostics without changing the authoritative plan. Each
entry keeps the run ID, source closure, command, actual result and the finding
needed for the next repair. Raw evidence remains under `studio/.local/`.

## 2026-09-30 — gt06-o5-host-soak-20260930-01

- Source closure: `01c76e467611fccf2dff2f5d8b0e0d0382bd438705230062ba2cccd0aa46671f`
- Command: `campaign_task.ps1 -Command register-run -CampaignId gt06-o5-host-soak-20260930-01 -Mode residency`
- Actual result: 35/35 batches, actual child and wrapper exit 0, clean Job/tree/handle.
- Finding: O1.4 private commit `max(5..34)/median(2..4)=123.781%` and late/early max `110.272%`; both exceed `110%/105%`. Diagnostic only.

## 2026-09-30 — gt06-o5-host-soak-20260930-02

- Source closure: `c04dbfc005185a33d576b2f4475b9a63c7b8e33dcf2d0c4d746bd737eb1c8ffc`
- Command: `campaign_task.ps1 -Command register-run -CampaignId gt06-o5-host-soak-20260930-02 -Mode residency`
- Actual result: 35/35 batches, actual child and wrapper exit 0, clean Job/tree/handle.
- Finding: O1.4 private commit `max(5..34)/median(2..4)=119.251%` and late/early max `112.714%`; both exceed `110%/105%`. Diagnostic only.

## 2026-09-30 — O5 repair verification

- Run: focused repair suite (not a campaign)
- Source: uncommitted O5 WIP; no formal closure minted
- Command: focused Python unittest suite for journal, replay, benchmark,
  environment, and measurement-window modules
- Actual result: exit `0`; `306 tests in 63.202s`; `OK`
- Finding: unit/integration contracts pass; long-run behavior and formal O1
  criteria remain unproven.

## 2026-09-30 — gt06-o5-host-soak-20260930-04

- Source closure: `ed42f2b8912f482dd597423a31e23d40cff2899f6232ca03ebfb860e1b299081`
- Command: `campaign_task.ps1 -Command register-run -CampaignId gt06-o5-host-soak-20260930-04 -Mode residency`
- Actual result: child terminated with a real exit record; Job/tree/handle
  clean; classification `PRODUCT_FAIL`; 27 completed batches.
- Finding: invalid-payload command `.b27.rejected.256` returned
  `CONNECTION_LOST_LOOKUP` instead of `INVALID_FIXTURE_PAYLOAD`. This is a
  bounded product diagnostic, not an infra abort and not a formal acceptance.
  The run's `journal-timings.json` counts `reload` as a journal-path
  invocation (including incremental/no-tail checks); `load=1` is the only
  full-file load. Do not report the reload counter as 64,182 full reloads.

## 2026-09-30 — gt06-o5-host-soak-20260930-03 (prior)

- Source closure: `6cd560efe44cb1a97be6709d32b355ea2e438da176551d59b2bb0b7ed811b709`
- Actual result: 35/35, child exit `0`, clean Job/tree/handle
- Finding: private commit batch 5 to 34 grew `+5.528084%`, over the O5 `<=5%`
  criterion; diagnostic only.

## 2026-09-30 — O6.2 journal live-state microbench

- Raw evidence: `8-9-hh3d-3/.local/reviews/o6-ram-microbench-20260930-01.json`
- Workload: one `VerifiedJournal` process, 35,000 logical commands, marks every
  1,000 commands, with committed/pending completion, dedupe lookup, leases and
  invalid-digest rejection. The JSONL journal was retained and the derived
  SQLite index was cleaned; this was a diagnostic process, not a campaign.
- Actual result: child exit `0` in `562.2765156` seconds. Live containers were
  `DiskCommands` and `DiskOffsets`; `pending=0` and `leases=0` at every mark.
  Tracemalloc current memory moved from `528,124` bytes at 1,000 commands to
  `552,792` at 35,000, with a `1,100,684`-byte peak. The private-byte series
  moved from `16,244,736` to `16,617,472` bytes, a tail increase of `372,736`
  bytes, about `10.96` bytes per logical command.
- Interpretation: this direct path is consistent with the O6.2 `<=32`
  bytes/command diagnostic slope and shows disk-backed command/offset
  containers. It does not prove the mixed host/editor O1.4 gate, editor
  handles, a formal pair, or product acceptance. Keep the raw artifact
  immutable and authority `0`.

## 2026-09-30 — O6.2 smoke-script verification

- Raw evidence: `8-9-hh3d-3/studio/.local/reviews/o6-ram-smoke-01/`.
- The reusable launcher passed `py_compile` and a 100-command smoke run with
  actual exit `0`, clean index cleanup and a retained journal guard. Private
  bytes were unavailable in that short process (`GetProcessMemoryInfo` error
  6), so this is only a launcher/cleanup check and contributes no O1.4 number.

## 2026-09-30 — O6.2 corrected 35k live-state microbench

- Raw evidence: `8-9-hh3d-3/studio/.local/reviews/o6-ram-20260930-02/`; supervisor
  exit record: `studio/.local/reviews/o6-ram-20260930-02-supervisor/process-exit.json`.
- Source closure: `b15f22fbecd4c1537ddf2d4c3e2509bdf9c10863ab667181965f3f1ade9e76ee`.
- Workload: 35,000 logical commands in one process, full 1k..35k mark series,
  committed/pending completion, dedupe, leases and invalid-digest rejection;
  `DiskCommands`/`DiskOffsets`, `pending=0`, `leases=1` (the bounded writer
  lease) at marks, and no derived-index leftovers.
- Actual result: child exit `0`, host supervisor captured exit `0`, elapsed
  `978.8726782798767s`; raw cleanup and journal guard passed. Private commit
  O1.4 observation: baseline median `17,952,768`, main max `18,440,192`
  (`102.715%`), late/early max `99.911%`; direct slope after 3k was
  `9.5514 bytes/logical command` and tracemalloc slope `8.5322`.
- Interpretation: O6.2 diagnostic threshold `<=32 bytes/command` is met and
  the live-state path is disk-backed. This remains authority `0`; it is not a
  mixed host/editor pair or GT06 acceptance. The corrected artifact supersedes
  the earlier mark-window smoke interpretation without rewriting that raw
  evidence.

## 2026-09-30 — gt06-o6-host-soak-20260930-01

- Source closure in the watchdog binding: `3ae3b69117a0d462849c38d56e161517477f3909eca2318f4e88c9e3b7f291bf`.
- Command: `campaign_task.ps1 -Command register-run -CampaignId gt06-o6-host-soak-20260930-01 -Mode residency`.
- Actual result: 28 batches completed; supervisor/child process exit was `1`, Job/tree/handles were clean, and `owner-failure.json` recorded `HARNESS_FAIL`.
- Finding: watchdog sample 198 raised `WATCHDOG_DOCKER_INVENTORY` while reading the explicit Docker Desktop endpoint. `watchdog-observation-error.json` and `watchdog-stop.json` were retained. This is an observer/harness failure, not O1 acceptance, not a product PASS, and not an `INFRA_ABORT`.
- Repair: Docker inventory now retries one transient read within the O4.1 sample budget and remains fail-closed on persistent uncertainty. Recovery validation was tightened in the same repair milestone; a fresh source closure and diagnostic run are required before formal consideration.