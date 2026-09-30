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
- Finding corrected under O6.3: exact O1.4 max/baseline is `116.4%` and
  late/early max `102.7%`; the growth limit fails. The historical batch 5 to
  34 comparison was `+5.528084%`; that retired formula is not the current gate.

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
- Actual result: 28 batches completed; `owner-failure.json` recorded `HARNESS_FAIL`.
  `owner/cleanup-001.json` records wrapper exit `2`, Job zero/closed and retained
  wrapper handle closed. There is no child `process-exit.json` or capture.
  Supervisor `return.json` says return `1` with actual process exit still
  unobserved; it is not a child exit record. Read-only Task Scheduler closeout
  on 30-09 later reports Ready/LastTaskResult `1` for this task.
- Finding: watchdog sample 198 raised `WATCHDOG_DOCKER_INVENTORY` while reading the explicit Docker Desktop endpoint. `watchdog-observation-error.json` and `watchdog-stop.json` were retained. This is an observer/harness failure, not O1 acceptance, not a product PASS, and not an `INFRA_ABORT`.
- The generic inventory code does not distinguish timeout, nonzero exit, OS
  error or malformed output. Do not attribute it specifically to a timeout.
- Separate memory finding: post-release baseline median batches 2-4 is
  `30,650,368` bytes; max 5-27 is `35,188,736` at batch 25 (`114.806896%`).
  This already breaches O1.4's `110%`; a completed suffix cannot undo that max.
  Partial late/early max is `103.096124%`, with batches 28-34 absent; handles
  stay at 182. No full-window PASS follows from this partial run.
- Next: short HTTP-path allocation attribution and bounded Docker query error
  diagnostics, then targeted repair/tests. Fresh preflight alone does not
  justify another long soak. Preserve all old raw and verdicts.

## 2026-09-30 — gt06-o6-host-soak-20260930-02

- Source closure: `b43fb6f19cd1f363c925fa82c1c8d9469d75e7191d9e5ac6305d21c04c40851e`.
- Command: `campaign_task.ps1 -Command register-run -CampaignId gt06-o6-host-soak-20260930-02 -Mode residency`.
- Actual result: all 35/35 host-only batches completed; child `process-exit.json`
  and owner capture both record exit `0`; Job assigned/configured/closed,
  active count `0`, zero observed, no retained handle, no failed operations,
  and natural tree exit. Task Scheduler closeout also returned `0`.
- O1.4 diagnostic values: batches 2–4 baseline median private commit
  `30,568,448` bytes; max batches 5–34 `32,743,424` bytes = `107.1151%`;
  early/late maximum is also `107.1151%`; handles stayed `182`; maximum
  status gap was `279.0004 ms`.
- Classification: complete host soak with clean exit/cleanup, but not O1
  formal acceptance and not a PASS for the O6.3 promotion trigger because
  growth is above the `107%` re-soak threshold (while below the formal `110%`
  ceiling). No editor pair, critic package, GT06 acceptance, or GT07 opening
  follows. Keep raw evidence immutable and run another fresh O6.3 soak only
  after review and a new O4.1 preflight.

## 2026-09-30 — HTTP allocation attribution and credential redaction repair

- Short HTTP diagnostic: `studio/.local/reviews/http-alloc-20260930-01/`;
  35 batches of **100** commands (3,500 total, not the formal 1,000 per batch),
  tracemalloc enabled, no editor. Actual exit 0 in 234.766s, producer closed,
  source unchanged. It cannot establish latency or O1.4 acceptance.
- Allocation snapshots after batches 4/19/34 show regex compiler live bytes
  `89,184 / 633,144 / 1,621,704`, counts `16 / 46 / 76`. Each credential
  rotation compiles two new secret-bearing patterns. Python's global regex
  cache retains obsolete cumulative secret sets; the bounded phase ring stays
  approximately constant. This identifies a real retention source, without
  attributing every byte of the prior host private-commit series to it.
- Isolated reproducer: `studio/tests/replay/run_redaction_residency.py --output
  <new-directory>`, 35 SessionAuthority generations (issue + 34 rotations), all issued secrets
  still checked for redaction. Before/after packages are
  `studio/.local/reviews/redaction-before-20260930/` and
  `studio/.local/reviews/redaction-after-20260930/`, both actual exit 0.
  Traced bytes at mark 34: `1,655,417 -> 38,546`; private bytes at marks
  4/19/34 before: `17,637,376 / 19,128,320 / 21,508,096`, after:
  `17,530,880 / 17,530,880 / 17,530,880`.
- Repair uses instance-owned literal matching, preserving leftmost-longest
  replacement and never rescanning inserted markers. It does not forget old
  credentials, clear global caches, enlarge the baseline, or change workload.
  Redaction tests cover overlap, metacharacters, Unicode, nonrecursive markers,
  exact old-matcher equivalence and a public-API spy proving rotations do not
  compile dynamic regexes.
- Docker observer repair shares the original total two-second budget across
  at most two reads and records a whitelisted cause (timeout/nonzero/OS/bad
  output). No exception text, argv or output is copied into the diagnostic.
  Its focused suite passes 42 tests, exit 0. Past generic errors stay unknown.
- Final script metadata/cleanup smoke `redaction-bound-20260930`: exit 0,
  source unchanged, PID/start/Python hash/import closure bound; 38,842 traced
  bytes at mark 34. Original before/after artifacts stay unchanged; their
  smaller metadata scopes are not upgraded retroactively.
- Regression: protocol 443 tests, exit 0 (4 skipped), 106.675s; replay 683 tests,
  exit 0, 120.748s. A maximal repeated-prefix literal check returned unchanged
  text in about 35ms; it is a local timing observation, not a latency gate.
- Remaining: freeze at dispatch, fresh O4.1 preflight and O6.3 host soak.
  Preflight 30-09 19:53 Asia/Saigon: available 6,225,252,352 bytes, commit
  92.164854%, no foreign engines; launch denied by resource limit. No new long
  run was dispatched. O2 work may continue separately. No acceptance claim.

## 2026-09-30 — O2 retry identity checkpoint

- Separate worktree commit `3db8c3e5` binds the gameplay-source retry digest to
  project/profile, command ID, expected revision, entrypoint and sorted source
  path/hash/size records. It validates and copies source bytes before cached
  ACK lookup; live grant/lease/deadline and owner state are rechecked for every
  retry. Ten pure adapter tests exit 0.
- This does not merge O2, close AUTH-02..04, or alter GT-06. Reopen dedupe,
  selector/journal crash recovery, concurrent admission, and full native
  runtime binding remain open and are recorded in `studio/AUTHORING_STATUS.md`.

## 2026-09-30 — latest resource gate observation

- Fresh read-only O4.1 preflight at about 20:20 Asia/Saigon: available memory
  `2,848,792,576` bytes, system commit `99.283519%`, foreign engines `0`,
  running Docker containers observed but allowed by O4.1. Result:
  `CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT`; no soak or engine was dispatched.
- This is an environment wait, not an INFRA_ABORT and not a product verdict.
  Do not close user applications or lower the launch/acceptance thresholds.
