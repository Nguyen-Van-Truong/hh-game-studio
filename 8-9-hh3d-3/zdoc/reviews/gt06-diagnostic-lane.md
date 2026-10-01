# GT06 diagnostic lane

## Hiện trạng

- WP: GT-06 chưa ACCEPTED; zero accepted formal pairs; GT-07 chưa mở.
- Residency source: 56 file, `172d7d0ce1b14d6302791fc2b4b9c2c242db72baa285dfae1fbda777098b62e8`; formal entry closure is separate and recomputed after `load_fixture()`.
- Profile v6: `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`.
- Run đo cuối: soak05 ngày 01-10 đủ 35/35, actual exit 0, cleanup/watchdog/source đã kiểm.
- O6.3 cũ: FAIL p95; private 106,6856% / trend 103,0091%, handles 183–184, gap 366,8387 ms.
- Probe03 production trim1: median lookup 108,5744%, append 106,5340%; không gộp trim64.
- O7: kiểm offline/version riêng trước formal09; không đổi verdict cũ hoặc threshold O1–O4.
- O6.5 offline control02 và formal08 reference PASS, không hồi tố (receipt o7-review-20261001-01).
- Preview cũ 21:47: RAM 2,49 GiB / commit 93,37%; foreign container hh-plan19-admission-20260919-r01; không dùng làm điều kiện hiện hành.
- Preflight O4.1 đầy đủ ngày 02-10 lúc 06:44: RAM khả dụng 13,523 GiB, commit 41,952%, foreign engines/containers 0; không tiêu INFRA budget.
- Chưa dispatch vì đã ngoài cửa sổ 22:00–06:00; kiểm lại source freeze, budget và CPU khoảng một phút trước formal09 ID mới.
- Sau offline đạt: một formal09 ID mới trong 22:00–06:00 với pair guard; không confirmation soak.
- O2 ở worktree riêng, AUTHORITY=0; chi tiết AUTHORING_STATUS.md; không merge trước GT06.

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
  late/early maximum is `97.0978%`; handles stayed `182`; maximum status gap
  was `279.0004 ms`.
- O6.3 timing calculation over logical command windows (batches 0–4 versus
  30–34) is also required. Lookup p95 is `3.59502 ms` to `4.45738 ms`
  (`123.9876%`), and append p95 is `15.43761 ms` to `18.59155 ms`
  (`120.4302%`). Both exceed the `120%` limit.
- Classification: complete host soak with clean exit/cleanup, but O6.3
  metrics **FAIL** on both journal timing checks. The private-commit growth is
  below the formal `110%` ceiling but above the `107%` variation threshold;
  that threshold is not the only failure. No editor pair, critic package,
  GT06 acceptance, or GT07 opening follows. The offline calculator and its
  pure tests are diagnostic only; raw evidence remains immutable.

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

## 2026-09-30 — gt06-o6-host-soak-20260930-03

- Source files matched the frozen O6-02 closure
  `b43fb6f19cd1f363c925fa82c1c8d9469d75e7191d9e5ac6305d21c04c40851e`.
- Command: `campaign_task.ps1 -Command register-run -CampaignId gt06-o6-host-soak-20260930-03 -Mode residency`.
- Actual result: watchdog stopped at batch 0 with
  `CAMPAIGN_WATCHDOG_OBSERVER_ERROR`; no batch/summary was admitted. The
  owner failure records `HARNESS_FAIL`, wrapper exit `2`, and
  `BENCHMARK_CLOSED_BEFORE_FINISH`. Job assigned/configured/closed, active
  count `0`, zero observed, no retained handle, and no failed operations.
- Classification: observer/harness failure only; not an INFRA_ABORT, product
  verdict, O1 pair, or O6.3 result. Preserve the raw observer error and review
  the Docker-query path before attempting another soak. Do not count this run
  toward the `>107%` re-soak requirement or dispatch formal09.

## 2026-09-30 — gt06-o6-host-soak-20260930-04

- Source closure: `b43fb6f19cd1f363c925fa82c1c8d9469d75e7191d9e5ac6305d21c04c40851e`.
- Command: `campaign_task.ps1 -Command register-run -CampaignId gt06-o6-host-soak-20260930-04 -Mode residency`.
- Actual result: watchdog stopped after batches `0..8` at sample `68` with
  `CAMPAIGN_WATCHDOG_OBSERVER_ERROR`. The Docker inventory observer recorded
  an explicit `timeout` after `2.219 s` on attempt 1. The owner failure is
  `HARNESS_FAIL`; wrapper exit is `2`, Job/tree/handle cleanup is closed and
  zero-observed, and no child `process-exit.json` was produced. Supervisor
  return code `1` is not a child exit record.
- Classification: repeated observer/harness failure, not an O6.3 result,
  `INFRA_ABORT`, product verdict, or acceptance. This is the third attempt in
  the bounded O6 diagnostic direction (O6-02 completed, O6-03 stopped at batch
  0, O6-04 stopped at batch 8). Do not dispatch another long soak from a fresh
  preflight alone. First make the observer path reproducible with a bounded
  short check that records timeout/nonzero/OS/bad-output causes, then either
  apply a targeted repair and rerun the short check or document its cost/risk
  and continue O2 while waiting for a clean environment. Never resume this
  run or any prior formal run; preserve all raw evidence. Options and cost/risk
  are recorded in `zdoc/reviews/20261001-o6-observer-options.md`.

## 2026-10-01 — gt06-o6-host-soak-20261001-01

- Source closure: `b43fb6f19cd1f363c925fa82c1c8d9469d75e7191d9e5ac6305d21c04c40851e`;
  profile `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`.
- Command: `campaign_task.ps1 -Command register-run -CampaignId
  gt06-o6-host-soak-20261001-01 -Mode residency`.
- Actual result: all 35/35 host-only batches completed. Child and wrapper exit
  `0`; Scheduler result `0`; Job assigned/configured/closed with active count
  `0`, zero observed, no retained handle, no failed operations, and natural
  tree exit. `result.json` records `source_unchanged=true`.
- O6.3 metrics from `residency_metrics.py`: **FAIL** only on
  `private_growth`; baseline median batches 2–4 was `29,814,784` bytes and
  max batches 5–34 was `32,804,864` bytes (`110.0288501%`). Handles stayed
  at `182`; maximum status gap was `527.0567 ms`; lookup p95 was `101.0764%`
  and append p95 `95.5321%` of the first logical window; load was `1` and
  transport recoveries were `0`.
- Classification: complete clean host soak with a product memory-gate fail,
  not `INFRA_ABORT`, not a formal pair, not acceptance, and not evidence for
  opening GT-07. The run is the independent `>107%` variation trigger and
  also crosses the `110%` O1.4 ceiling. Keep raw immutable; do not dispatch a
  formal run or repeat a long soak before a bounded memory/index diagnosis.

## 2026-10-01 — bounded HTTP allocation diagnosis and journal sidecar repair

- Initial `o6-memory-attribution-20261001-01/run.py` used 10 tracing frames
  and produced only batch 0 before losing its process/tool observation. No
  actual exit, complete result or cleanup proof is available. Preserve it as
  incomplete, not PASS, and do not resume it. Lesson: deep tracing materially
  distorts this HTTP workload; use one frame and bounded supervision.
- `http-alloc-20261001-01/probe.py` completed 35 x 100 commands (3,500 total)
  with one tracing frame in 315.11 seconds; captured child exit 0, clean Job,
  tree and handles, producer closed, source unchanged. Closure:
  `15337fb2fd9a10e6a9234e6818b6d376b6f386596c602777010861121b8bc046`.
  It is not the 35,000-command soak or an O1.4 result. Live traced allocation
  increased from about 2.64 MB to 3.63 MB; snapshot 19 attributed 961,600
  bytes to `pathlib.py:74` (`sys.intern`). The phase ring remained bounded.
- Isolated `path-intern-20261001-01/probe.py` ran 200,000 repeated guard/lock
  name evaluations in each of two fresh interpreters, both actual exit 0.
  Rebuilding names retained 967,384 traced bytes (961,216 at pathlib's intern
  call), versus 6,168 when the same two Path objects were retained. Private
  bytes increased 1,798,144 versus 4,096. This proves a source of allocation,
  not attribution of every byte of the prior soak. The isolated raw records
  script hash and Python version, not a full imported-source closure.
- Repair retains only the journal's two derived sidecar names, keyed by its
  current path. Every namespace lstat, guard open/fstat, kernel lock and
  metadata recovery check still executes. No global cache purge, baseline
  padding, workload reduction or gate/timeout change is introduced. Focused
  tests cover bounded retained allocation, path changes, and unsafe aliases
  introduced after cache population.
- O3 direction closeout (three diagnostic attempts): (1) selected: validate
  this demonstrated repair with regressions and the existing 35,000-command
  direct microbench, then one fresh O6.3 soak if it passes; cost roughly a few
  minutes of tests plus the prior microbench's 16-minute runtime, risk that
  other native allocator variation remains. (2) Keep diagnosing unrelated
  allocation sites: higher cost with no current evidence, so deferred.
  (3) Continue O2 if the environment or validation prevents measurement;
  GT06 remains open. No further blind diagnostic/soak loop is authorized by
  this note, and no formal dispatch follows before all O6 prerequisites.
- Static implementation review found that Windows Path equality can fold case
  despite a case-sensitive directory. Cache invalidation now uses immutable
  Path identity, with an exact-spelling reassignment regression. Final tests
  recorded under `sidecar-verify-20261001-01`: protocol **447** (4 skipped),
  replay **693**, both actual exit 0 and unchanged source. The earlier replay
  run rejected the changed journal with `REPLAY_REUSE_SOURCE_CHANGED`; only
  the installed execution binding/selector was refreshed, leaving GT05's
  accepted manifest unchanged. An intervening protocol tool handle vanished
  with no terminal proof; it was not counted.
- Direct microbench `o6-ram-20261001-03` was launched from the tool session
  and stopped after 30,000 commands without a captured exit/result. Do not
  infer completion or resume it. Brief O2 pure tests also overlapped its early
  window, so it is not clean O6.2 evidence. The next validation uses an
  independent demand task with retained Job supervision, persisted actual
  exit, measurement lock and watchdog; no competing tests are allowed.

## 2026-10-01 — O6.2 journal validation closeout

- `o6-ram-20261001-04` was a one-use demand task with clean Job setup but
  stopped before child start at `BENCHMARK_WORKSPACE_LIMIT`: its working
  directory scanned the existing `.local` corpus. This is a harness boundary,
  not a memory verdict. Raw supervisor exit and closed zero-observed Job are
  retained; the task was deleted only after `actual_instances=0`.
- `o6-ram-20261001-05` reran with an isolated workspace and separate output.
  It completed 35 marks/35,000 logical commands. Child actual exit and
  supervisor exit were both `0`; Job assigned/configured/closed with active
  count `0`, zero observed and no retained handles. Result is
  `PASS_DIAGNOSTIC`, not product acceptance. Source closure was
  `b9fb8c284c3c26db317987dbc53989e64cfdf57a79679e58ac2816920fbd8538`.
- O6.2 measurements: baseline median `17,842,176` private bytes; maximum
  `18,227,200` (`102.1579%`); late/early maximum `101.3437%`; private slope
  `13.7295` bytes/logical command; `diagnostic_gate_codes=[]`; invalid
  rejections `10,500`, index leftovers `[]`, source unchanged. This confirms
  the bounded journal/index direction under its direct mixed-host workload.
  It is not an O1.4 pair, editor result, or reason to lower a gate.
- Next action is one fresh O6.3 host-only 35-batch soak after a new source
  closure and O4.1 preflight/CPU observation. No formal pair is allowed before
  that soak and its timing/memory/cleanup checks pass. Raw diagnostics remain
  under `.local`; no old run is resumed.

## 2026-10-01 — O6.3 observer repair and fresh dispatch readiness

- `gt06-o6-host-soak-20261001-02` was terminal before completion: batches
  `0..13`, sample `92`, `CAMPAIGN_WATCHDOG_OBSERVER_ERROR` from the PerfProc
  query. It is a `HARNESS_FAIL`, not an O6.3 result, `INFRA_ABORT`, product
  verdict, or formal pair. The supervisor had no child actual-exit record, but
  its Job/tree/handle cleanup is closed with active count `0`, zero observed,
  and no retained handle. The exact task was deleted only after that cleanup;
  raw evidence remains under `.local/reviews/gt06-o6-host-soak-20261001-02/`.
- Repair commit `50fc45c1` bounds PerfProc queries to two attempts under one
  eight-second deadline, preserves unknown counters on empty/partial provider
  output, rejects late/malformed/duplicate rows, and persists only whitelisted
  diagnostics. Regression commit `e12268eb` adds the failure/retry/shape and
  secret-suppression cases; focused suite is **50 tests, exit 0**. A separate
  12-call provider probe also returned exit `0` on every call (diagnostic only).
- Fresh source closure after the repair/test commit is
  `46bfe26f04d6dc4e73cf3f18fc35a9974cd957ce2a232ce2e36b3d85206b9915` (54
  files). O4.1 preflight/CPU observation `soak-preflight-20261001-03` ran for
  about one minute: available memory stayed `5.66–7.18 GiB`, commit
  `72.93–75.57%`, no foreign Godot/Blender engine, and no external process
  reached the 50% CPU abort threshold. This is launch readiness only.
- The next permitted action is one fresh host-only O6.3 35-batch soak with a
  new ID and this frozen closure. Do not run formal09 until its actual exits,
  cleanup, timing and O1.4 memory/handle/status metrics pass; if private
  growth exceeds 107%, perform the required additional soak with another ID.

## 2026-10-01 — O6.3 Docker observer window check

- `gt06-o6-soak-20261001-03` reached only batches `0..4` before the watchdog
  stopped on `WATCHDOG_DOCKER_INVENTORY`: Docker query attempt 1 timed out at
  `2.094 s` (sample `35`). It is `HARNESS_FAIL`, with no O6.3 metric/result,
  no child actual-exit record, and no product/formal verdict. Job/tree/handle
  cleanup is closed, active count is `0`, zero observed, and no handle is
  retained. The scheduler task was deleted after status and cleanup checks;
  raw evidence remains under `.local`.
- A separate bounded read-only Docker probe at `docker-observer-probe-20261001-02`
  queried the fixed Docker Desktop Linux named pipe and returned the validated
  nine-container inventory in `2.625 s` wall time (the query itself stayed
  within its two-second observer budget). This is an environment-window check,
  not a soak result or acceptance proof; it does not justify changing any
  timeout or accepting stale inventory.
- With no live campaign and the same verified closure
  `46bfe26f04d6dc4e73cf3f18fc35a9974cd957ce2a232ce2e36b3d85206b9915`, the next
  action is a fresh O4.1 preflight/CPU observation followed by one new O6.3
  host-only ID if the observer remains responsive. Do not resume this run,
  start formal09, or treat the five-batch prefix as evidence.

## 2026-10-01 — Docker observer repair and O6.3-04 closeout

- `gt06-o6-soak-20261001-04` used the previous CLI observer and stopped at
  batches `0..4` (sample `33`) with `WATCHDOG_DOCKER_INVENTORY`, attempt 1
  timeout `2.391 s`. It is `HARNESS_FAIL`, not O6.3, `INFRA_ABORT`, product
  FAIL, or a formal pair. Job/tree/handle cleanup is closed with active count
  `0`, zero observed, no retained handle, and no child actual-exit record.
  The task was deleted after those checks; raw remains immutable.
- Targeted repair commit `daffb01a` replaces repeated Docker CLI startup with a
  direct read-only HTTP GET on the fixed Docker Desktop Linux named pipe. It
  keeps the Docker-process gate, one shared two-second deadline, bounded HTTP
  headers/body, strict status/content framing/JSON/name/state validation, no
  stale cache, and sanitized fail-closed diagnostics. Native pipe coverage is
  in `891e14be`: 3 tests exit 0 (fragmented response/request, stalled read
  cancellation, malformed response cleanup). The pure/direct suite is 80 tests
  exit 0; replay discovery is **731 tests, exit 0**. A separate authority-0
  direct-vs-CLI probe matched nine names; direct calls were roughly 32–62 ms
  versus CLI 109–157 ms. A 100-call direct lifecycle probe reached at most
  219 ms, with no retained pipe/handle and unchanged source. These probes do
  not constitute O6.3 or formal acceptance.
- New measured source closure after this repair is
  `172d7d0ce1b14d6302791fc2b4b9c2c242db72baa285dfae1fbda777098b62e8` (56
  files). Fresh O4.1 preflight/CPU samples had passed before the prior soak;
  a new preflight is required at dispatch. Next action is one fresh host-only
  O6.3 ID with this closure. Do not resume any terminal run or dispatch
  formal09 until actual exits, cleanup, O1.4 memory/handle/status and timing
  metrics pass; private growth above 107% requires the extra fresh soak.


## 2026-10-01 — O4.1 preflight block after Docker observer repair

- A fresh O4.1 observation was attempted as `soak-preflight-20261001-06`
  against source closure `172d7d0ce1b14d6302791fc2b4b9c2c242db72baa285dfae1fbda777098b62e8`
  (56 files). All seven samples were structurally captured, with available
  memory `2.19–3.77 GiB` and commit `78.77–82.16%`; foreign Godot/Blender
  engines and hot external CPU were absent, but every sample failed the
  O4.1 available-memory requirement of `>=4 GiB`. No O6.3 task was
  registered, and no campaign/engine workload was started.
- The initial preflight attempt hit `WATCHDOG_PERF_COUNTER_QUERY` before its
  first sample. A bounded exact-query follow-up completed in `1.375 s` and
  returned sanitized PerfProc rows; this is an observer diagnostic, not a
  preflight pass. The failed preflight is an environment block, not
  `INFRA_ABORT`, product FAIL, O6.3 evidence or formal evidence.
- The direct Docker observer repair remains covered by `daffb01a` and
  `891e14be`: native/direct suites and replay discovery were green, but no
  acceptance is inferred. Next action is to wait for a fresh O4.1 pass, then
  register exactly one new host-only O6.3 ID. Do not lower the 4 GiB gate,
  resume a terminal run, or dispatch formal09.

## 2026-10-01 — Fresh O6.3 confirmation dispatched

- Resources changed after preflight06. `soak-preflight-20261001-07` captured
  seven passing O4.1 samples over about 65 seconds: available minimum
  `4.2145 GiB`, commit maximum `84.1018%`, no foreign engine and no hot
  external process. Daily recorded INFRA_ABORT count was zero.
- Dispatched `gt06-o6-soak-20261001-05` at `09:49:03 Asia/Saigon` using
  `campaign_task.ps1 -Command register-run -CampaignId gt06-o6-soak-20261001-05 -Mode residency`.
  It uses the unchanged 56-file closure `172d7d0ce1b14d6302791fc2b4b9c2c242db72baa285dfae1fbda777098b62e8`.
  This is one confirmation of the reviewed Docker observer repair, not a
  resumption of -04, a formal pair or a completed O6.3 result. At the first
  readback, batches 0 and 1 were complete and the scheduler instance was live;
  measurement-window.lock was held for this exact run.
- While live, only read status/evidence. Terminal review must verify actual
  exits, Job/tree/handle cleanup, watchdog and source before offline O6.3
  metrics. No new long run without that review. The app heartbeat
  `theo-d-i-o6-3-v-ti-p-t-c-gt06` now checks this checkpoint every 20 minutes;
  the old heartbeat ID no longer exists.

## 2026-10-01 — O6.3-05 complete; latency gates fail

- `gt06-o6-soak-20261001-05` completed 35/35 in about 20.4 minutes.
  Actual child exit 0 (PID 31612), wrapper exit 0 and Scheduler result 0/no
  instances. Offline `benchmark_job.verify_capture` and watchdog replay
  passed; retained/live 56-file source still equals `172d7d0ce1b14d6302791fc2b4b9c2c242db72baa285dfae1fbda777098b62e8`.
  Natural tree exit, Job active 0/closed, no retained handle, empty stderr.
  The exact demand task was deleted only after closeout. Proof is
  `studio/.local/reviews/gt06-o6-soak-20261001-05/closeout-check.json`.
- `residency_metrics.py --run-directory .local/reviews/gt06-o6-soak-20261001-05`
  returned exit 1: private baseline 31,674,368 bytes/max 33,792,000
  (`106.6856%`, late/early `103.0091%`), handles 183–184, max status gap
  366.8387 ms, load=1, one reconciled transport recovery. These checks pass
  and private growth does not trigger the >107% additional-soak rule.
  Lookup p95 first/last = 3.57274/4.55176 ms (`127.4025%`); append =
  15.38933/19.73632 ms (`128.2468%`). Both exceed 120%, so O6.3 FAIL,
  AUTHORITY=0, no formal dispatch. It is not an INFRA_ABORT or harness stop.
- Bounded latency diagnosis starts 10:11 Asia/Saigon (O3: four hours/three
  diagnostic attempts). Per-batch times are nonmonotonic, so do not infer
  history-size complexity alone. First seeded probe compares the 4.86 MB and
  34.18 MB retained states using alternating common-key lookups; raw untouched,
  actual exit 0. A second probe tests repeated pager trimming as a hypothesis
  on separate copies; no production source or gate has been changed.

### O3 latency direction closed after three short probes

- Fresh copy probes `journal-latency-seed-20261001-01`, `-02`, `-03`
  each completed with actual exit 0 (`python -u <probe-directory>/probe.py`).
  They preserve source journal bytes; live 56-file residency source still
  matches `172d7d0ce1b14d6302791fc2b4b9c2c242db72baa285dfae1fbda777098b62e8`.
  Probe03 also records its conservative imported-source closure before/after.
  These are short AUTHORITY=0 comparisons, not O6.2/O6.3 or formal evidence.
- Probe01 alternated lookups on 4.86 MB and 34.18 MB retained states: the
  larger state was often faster, with one noisy block. Probe02's early
  apparent cache improvement disappeared substantially in later baseline
  blocks. Probe03 balanced six randomized rounds of both sizes and trim
  intervals 1/64 (1,200 command cycles, 1,800 durable appends), recording
  CPU, process memory, SQL and Python fsync duration. At matched low CPU
  (25.97%/26.08%), trim64 did not improve early-state append or lookup p95.
  At matched higher CPU (61.57%/62.92%), late-state trim64 was slower:
  append 14.956 -> 16.420 ms; lookup 3.965 -> 4.553 ms. Combined-process
  memory is not a per-variant memory proof. No production trim change.
- Offline alignment of soak batches with environment samples found mean
  total CPU 31.54% in the first-five window versus 50.88% in the last five.
  The correlation JSON is retained with soak05. This is a timing association,
  not root-cause proof, and the recorded watchdog did not trigger; soak05
  remains O6.3 FAIL, not INFRA_ABORT. Do not discard spikes or select a
  favorable subset for acceptance.
- O3 limit reached (3/3 attempts; direction started 10:11 Asia/Saigon).
  Options: (1) keep source and run **one** fresh quiet-window confirmation,
  about 20–25 minutes after existing O4.1/CPU observation; outside load can
  return; (2) change cache trimming only after better controlled evidence,
  with regression and a new 35k RAM microbench, risking memory regression;
  (3) advance fixture O2 independently while waiting. Choose (1)+(3).
  Prefer 22:00–06:00 local for the confirmation; this selects a time and
  does not alter preflight, watchdog, timeout or metric thresholds. Do not
  start a fourth seed probe, a daytime blind rerun, or formal09. A further
  O6.3 failure needs fresh review, not automatic repeated soak dispatch.
  Current source remains verified; a fresh freeze/preflight is still required
  immediately before the next measurement.

## 2026-10-01 — O7 reviewer corrections and offline review

- Reviewed commit `56c37fc5` against retained raw. Soak05 memory/handle/status
  numbers reproduce. Formal08 reference recomputes host peak/baseline
  `125.7653%`, late/early `108.8589%`, growth `10,342,400` bytes. These are
  different workloads/sources; no claim that all earlier formal failures are fixed.
- Probe03's quoted `106.5%/105.9%` pools production trim1 and experimental trim64.
  All six production blocks per state yield lookup `2.1914 -> 2.3793 ms`
  (`108.5744%`) and append `9.9617 -> 10.6126 ms` (`106.5340%`). Six-round
  Random(61001) order and 50 lookups/75 appends per block are intact. Original
  seeds have 7,015/49,105 records (7x); all 48 runtime hashes and 56 soak hashes
  match live, with 17 shared files agreeing. Probe closure did not include
  probe.py or its percentile helper; newly recorded hashes do not repair that
  historical coverage. This is bounded evidence, not a proof of asymptotic complexity.
- CPU means differ even within production blocks. CPU association and median
  ratios do not establish that p95 growth is entirely external load. O7 now
  preserves raw tail metrics, legacy O6.3 FAIL, and absolute O1/TQ gates. New
  O7 offline checks must complete before dispatch; no forced exit0 or missing
  evidence treated as PASS. No fourth latency probe was run.
- Removed the proposed automatic 30-second observer sample gap: mandatory
  CPU/engine/container observation still obeys O4.1 <=10 seconds. Failure
  branches require phase evidence/reproducer, not a preselected speculative fix.
  Task cleanup requires terminal/closeout and no live instance; Ready alone is
  insufficient. AGENTS now distinguishes O7.5 static preparation from opening GT07.
- `verify_editor_handle_control.py` actual exit0 on control02 and formal08
  reference, retaining source/profile-bound raw. Control baseline564,
  early/late medians556/554, max566; formal reference baseline558,
  early/late554/555, max562. New receipts are in
  `studio/.local/reviews/o7-review-20261001-01/`; no historical verdict changed.
- Resource preview at 21:47 had available2.49055GiB, commit93.37299%, and an
  unrelated running hh-plan19 container. No campaign dispatched or app stopped;
  this preview is not an INFRA_ABORT attempt. Fresh O4.1/CPU/budget checks remain
  required immediately before the permitted formal window.

## 2026-10-01 — O7 offline verifier and formal closure review

- `residency_metrics.py --policy O7` ran against the retained soak05 and probe03
  with actual exit `0`. O7's finite diagnostic checks pass: production interval=1
  lookup `108.5744%` and append `106.5340%`; the embedded legacy O6.3 result
  remains `metrics_pass=false` for lookup/append p95 and is preserved in the
  output. The report is authority 0 and cannot sign formal acceptance.
- The command-bound source closure was recomputed through the real formal entry
  path: after `load_fixture()`, host-only soak05 is 56 files /
  `172d7d0c…`, while the formal campaign candidate is 58 files /
  `bc00a2aef953f068a122ec9ecaa48242db453cc73ef97e3eb31b5befd60f6e58`.
  The extra formal imports are `godot-addon/fixture_profile.py`,
  `godot-addon/bundle_staging.py`, and `godot-addon/bundle_v2.py`; the soak-only
  `tests/replay/run_command_residency.py` is absent. These closures must remain
  separate and the formal closure must be frozen again at dispatch. Profile
  remains v6 `8a2e599c…`.
- A fresh pre-dispatch observation at 22:08–22:09 Asia/Saigon had available RAM
  `13.066 GiB` minimum, commit `47.285%` maximum, CPU `14.198%` maximum over
  three samples, and zero foreign Godot/Blender engines. It is a readiness
  observation, not an INFRA attempt; O4.1 must still run before each formal pair.
- A later read-only O4.1 snapshot at 22:20 recorded available RAM `9.883 GiB`
  and commit `54.769%`, but still found the unrelated Docker container
  `hh-plan19-admission-20260919-r01` as a foreign engine/toolchain entry. The
  snapshot is `pass=false`; no task was dispatched, no budget was consumed, and
  the container was not stopped. Formal dispatch remains gated until a new
  snapshot has zero foreign engines and the one-minute CPU observation is clean.

## 2026-10-02 — O7 binding hardening and dispatch hold

- The offline verifier was rerun after binding seeds to the retained soak journal
  prefix and exact batch journal sizes. Actual exit is `0`; O7 remains
  `metrics_pass=true`, authority `0`, while the embedded legacy O6.3 result is
  still `metrics_pass=false` for both p95 checks. The bound original seeds are
  `7,015` and `49,105` JSONL records and match the batch-04/batch-34 prefixes.
- Focused pure tests now pass: residency/O6.3+O7 `12/12`, retained-probe binding
  `6/6`, actual exit `0` for each suite. They exercise altered prefixes, rehashed
  caller claims, forged summaries, missing blocks, nonfinite values, and the
  excluded trim64 experiment. No engine, Docker or measurement workload ran.
- A clean formal-entry computation in a fresh Python process after
  `load_fixture()` produced `58` files and closure
  `bc00a2aef953f068a122ec9ecaa48242db453cc73ef97e3eb31b5befd60f6e58`; this is
  recorded under `studio/.local/reviews/o7-review-20261001-01/` and is not yet a
  dispatch freeze. The 56-file residency closure remains historical evidence.
- Formal09 was not dispatched: the last O4.1 snapshot found foreign Docker
  container `hh-plan19-admission-20260919-r01`, and the 22:00–06:00 window has
  ended. No app/container was stopped and no INFRA budget was consumed; a new
  one-minute CPU observation, zero foreign engines, source freeze and daily
  budget check are required in the next permitted window.
- At 06:44 Asia/Saigon the foreign container had terminated naturally. A fresh
  read-only preflight recorded `pass=true`, available RAM `13.523 GiB`, commit
  `41.952%`, zero foreign engines and zero running containers. This was outside
  the 22:00–06:00 dispatch window, so it did not launch a task or consume budget;
  it is only a readiness receipt for the next window.
