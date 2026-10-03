# GT06 diagnostic lane

## Hiện trạng

- GT-06 chưa ACCEPTED; zero accepted formal pairs; GT-07 chưa mở. Formal21 là PRODUCT_FAIL status gap 2766.6174 ms; không resume run cũ/S258.
- Formal09 pair0 PASS 35/35 nhưng pair1 INFRA_ABORT; formal10 PRODUCT_FAIL; formal11/17/19 HARNESS_FAIL; formal14/21 PRODUCT_FAIL; verdict/raw giữ nguyên.
- O9.2 lifecycle, O9.3 role binding và O9.4a telemetry đã harden; O1/O4 thresholds, timeout và phân loại cũ không đổi.
- Wake-lag cleanup, retry binding, NaN/overflow window guard và source-closure binding đã có regression coverage; vắng telemetry thì fail-closed.
- O9.4D I/O/Godot source review chỉ là chẩn đoán; chưa chứng minh nguyên nhân status-gap/save-tail.
- O9.4C chưa đạt: chain-f22-r01 đã chạy nhưng host INFRA_ABORT CPU ngoài sau một batch; formal22 chưa dispatch. Ngày 03-10 đã có hai host INFRA_ABORT, không chạy thêm GT06 ngày đó.
- O9.5b đã có mode Scheduler quiet-chain độc lập chat, hash frozen plan, actual host capture, combined watchdog và exact source/profile trước formal.
- O7 reader tách control gốc/host mới; chỉ chấp nhận profile normalization CRLF→LF đã pin, không hồi tố raw/hash/verdict hoặc giảm ngưỡng.
- Host/watchdog/formal dùng chung closure 64 file; lấy hash freeze từ quiet-chain-plan.json của scheduler, không dùng hash candidate cũ trong chat.
- Closure trên chỉ là candidate; phải freeze lại sau khi source dừng thay đổi, rồi O4.1 + CPU-minute mới trước mọi run.
- Formal mới chỉ được dispatch trong cửa sổ yên, không workload cạnh tranh, còn INFRA budget, và không đóng app/container ngoài ownership.
- Nếu metrics/status-gap/cleanup/source drift fail, giữ raw và dừng; không retry mù, không hạ gate, không tự ACCEPT.
- Sau hai pair formal PASS cùng closure mới lập CRITIC_PACKAGE O4.3 cho owner; không tự gọi critic/ký ACCEPTED.
- O2 fixture/adapter/particle worktree vẫn AUTHORITY0, không merge trước GT06; GT07 chưa mở.
- Bằng chứng chi tiết và các verdict lịch sử nằm ở các mục bên dưới; raw mới giữ riêng dưới `studio/.local/`.

This lane records diagnostics without changing the authoritative plan. Each
entry keeps the run ID, source closure, command, actual result and the finding
needed for the next repair. Raw evidence remains under `studio/.local/`.

## 2026-10-03 — Scheduled quiet chain r01 closeout

- `gt06-o9-chain-f22-r01` / host `gt06-o9-host-f22-r01`: INFRA_ABORT `EXTERNAL_CPU_PRESSURE`, 1 completed batch, max gap323.6126ms; formal22 never started.
- Closure64 `001fbebff68d225a861890dd05b9b841ed76417750064251255bbe359928dd0f` rehashed unchanged. Scheduler return1, helper wrapper2; actual/natural child exit UNKNOWN, not PASS. Job zero/closed and owned handles unretained; both observed PIDs absent.
- `python -B studio/tests/replay/closeout_quiet_chain.py --campaign-id gt06-o9-chain-f22-r01 --write --delete-task` exited0; exact task deleted, XML/raw retained and hashed at `studio/.local/reviews/gt06-o9-chain-f22-r01-closeout`.
- Common closeout tests: 23 cases, 22 passed + 1 Windows symlink privilege skip, exit0. Utility is outside measured runtime closure; diagnostic administrative cleanup does not grant acceptance.
- Along with host-soak-20261003-01 this reaches two INFRA_ABORT today; no further GT06 dispatch today. Continue O2; later fresh run requires genuine resource relief and current O4.1/CPU-minute, never cumulative CPU or app-name guesses.

## 2026-10-03 — O9.5 scheduled chain and retained-control repair

- Fixed undefined residency clock and dead-child padding; active same-producer extension is bounded at 64, with all-batch gap checks and first-35 O6.3 unchanged.
- One host+watchdog run now satisfies O9.5 combined diagnostic when verified, with replayed streams and hash-bound actual exit/capture; no duplicate 30-minute observer run.
- Scheduled quiet-chain binds its saved dry-run; formal request and child both verify frozen source/profile. Wrapper return alone remains insufficient for closeout.
- Retained O7 readiness verified offline: 48 dependency files compatible, one exact mixed-CRLF normalization; lookup 108.5744%, append 106.5340%. Original seeds remain bound to original soak05, never the new journal.
- 264 focused replay/command/environment/scheduler/O7 tests passed, actual exit 0; PowerShell parse and diff checks passed. No new native/formal PASS claimed.

## 2026-10-03 — O9.2/O9.3 closeout and O9.4 diagnostics

- `gt06-o9-io-probe-20261003-02` completed 20,000 iterations with actual
  process exit 0. Open/read max was 12.0503 ms; ReplaceFileW/os.replace max
  was 96.483 ms; append+flush+fsync max was 580.682 ms with one tail ≥500 ms.
  Defender/SearchIndexer CPU counters were captured before/after. The probe is
  diagnostic only (`formal_acceptance=false`); no latency is subtracted from
  O1 and no root cause is claimed. Raw result remains in its own `.local`
  directory.
- `gt06-o9-host-soak-20261003-01` used the new closure after preflight and
  terminated at watchdog sample 31 with `INFRA_ABORT /
  EXTERNAL_CPU_PRESSURE`. Actual owner Job was closed/zero with no retained
  handle; raw stream and `watchdog-stop.json` are preserved. External load
  included vmmemWSL, Chrome, rustc and node, so this is an invalid O9.4C
  quiet-window soak, not a product verdict and not a reason to lower gates.
- O9.4D source review is complete against the official Godot 4.7.2-stable
  source: `FileAccessWindows::_close()` attempts `ReplaceFileW`, falls back to
  `MoveFileW`, and retries up to 1000 times with 1 ms sleeps when the target is
  locked; failure reports safe-save failure. The exact source is not vendored
  in this repository, so this is provenance evidence rather than a local
  closure file. Reference: https://github.com/godotengine/godot/blob/4.7.2-stable/drivers/windows/file_access_windows.cpp#L223-L260.
  The I/O result remains diagnostic only; no O1 gate/timeout is changed. The
  next valid action is a quiet host-only soak after workload reduction, then a
  final watchdog soak on the exact frozen closure.

## 2026-10-02 — Save-return ordering guard, distinct from latency attribution

- Static audit found `_save()` publishes SAVE_WAIT before invoking the native API.
  A synchronous scene_saved followed by nested processing could read back and advance
  to RELOAD before that API returns. This conditional ordering defect is not proof of
  naturally occurring reentry or the5.077626s formal14 stall. A read-only scoped agent
  independently confirmed the narrow guard; this is not an acceptance critic.
- Added a per-save completion latch: reset before SAVE_WAIT, set only after native
  returnOK and no prior failure; `_wait_save()` waits for it. Heartbeat and all deadline,
  signal/path/count/hash/reload checks stay active. Save API/preview/profile/timeouts
  are unchanged. Supplemental diagnostic patch anchors were updated.
- Fault runner copies the real GDScript driver, replacing only the save-call expression
  and overriding adapter readback/failure capture in a test subclass. It exercises
  synchronousOK/error, delayed/wrong/duplicate signal, next-cycle reset, timeout and
  unhidden status gap. It does not execute a real save or prove latency improvement.
- `gt06-save-boundary-20261002-01`: old driver target29432 exit41, wrapper41,
  outer1;9 of27 checks fail (premature readback/reload, including before later error).
  Natural tree exit and Job zero/closed observed. Startup scan-aborted warning is
  retained; the harness now waits for filesystem scanning before completing.
- `...-02`: repaired driver target18772 actual exit0, wrapper/outer0,27/27,
  clean stdout/stderr, natural tree exit, Job closed/zero/unretained. Marker PID and
  exact unique check set were additionally reverified offline; no extra engine run.
- `...-03 --real-save`: original preview-enabled save plus one forced `_process(0)`
  at its real scene_saved callback. Actual import32704/editor36144 exits0, native
  save/hash/semantic-reload diagnostic completed, both Jobs closed/zero/unretained.
  Outer verifier originally exit1/BOUNDARY_REAL_ADVANCED because `recorded` meant
  key presence: `_begin_cycle` already creates an empty saved_file_sha256 field.
  Preserve that failed outer verdict. Corrected verifier has regression tests.
- New `...-03/offline-boundary-review.json` independently verifies both stage
  captures,57 frozen source files and16 final project files. Before/after forced
  reentry: SAVE_WAIT, completed=false, end_us0, stable root/batch/cycle. Lack of
  hash publication/readback is inferred from the frozen guard, not a sampled hash
  value. Corrected phase check is true; this does not retroactively change outer1.
- Focused native-benchmark/save-marker suites15 tests and boundary suite4 tests
  actual exit0; native fault suite27 checks. Empty/duplicate/failed check sets and
  mismatched PID are rejected; measurement release also checks retained Job/probe
  registries. No broad suite or repeated native measurement was required.
- All three IDs are terminal, raw and ZIP manifests retained. Direction budget3/3;
  do not resume or rerun merely to get a green outer banner. This repair closes an
  ordering hole but does not establish formal14 root cause or authorize formal15.
  Continue O2 registered adapter work while selecting a reviewed latency direction.

Archive manifests (AUTHORITY0, raw preserved):

- `gt06-save-boundary-20261002-01/raw.zip`: 8d90897e0bd12e6b9bfdc455efc3bdaec3cbce766bb39e06ac4a791b2ee6f557 (3611655 bytes).
- `gt06-save-boundary-20261002-02/raw.zip`: 0ba9c983f78500eb4436df0399a3e5eb80ab01d1394abbeda73cdf8616f4aba0 (3613099 bytes).
- `gt06-save-boundary-20261002-03/raw.zip`: 5e6804c21f0110766c0177c9259d15752fc78ef4c23ed70ddea6cec209212b77 (7126406 bytes).

## 2026-10-02 — formal14 closeout and native save localization

- Windows arm dispatched formal14 at18:48 after a fresh O4.1/CPU minute. The
  campaign ended19:06:13 with PRODUCT_FAIL / CAMPAIGN_STATUS_GAP, 14 captured
  batches and no complete pair. Native batch13 and ACK report5077.626ms,
  start permit529.257ms, host124.8732ms. Old raw/verdict remain unchanged.
- Heartbeats at native ticks994784408 (cycle84/RELOAD_WAIT) and999862034
  (cycle85/SAVE_WAIT) delimit the gap. Cycle85 save starts994912948, signal
  arrives1000004933 and readback completes1000042836: save5129.888ms,
  before signal5091.985ms, after signal37.903ms; reload27.690ms.
  This localizes the slow path to native save/signal delivery, but there is
  no call-return timestamp to distinguish a synchronous save block from a
  later callback. CPU, disk and root-cause attribution remain unproven.
- Host PID29960 actually exited1. Host/editor owners report zero active Job
  members, closed Jobs and released wrapper handles; editor target exit was
  not recorded, so cleanup must not be described as natural exit0.
  Current/frozen58-file hashes and84 captured batch references match.
  Offline watchdog replay completed exit0 with no stop; it does not relabel
  this product failure as infrastructure. Both exact scheduler tasks were
  removed after terminal/cleanup validation, retaining XML and deletion receipts.
- Diagnostic `gt06-status-gap-save-diagnostic-20261002-01` used a disposable
  100-cycle copy with the20-second production-stage runner by mistake. It
  stopped at20.141s with STAGE_WALL_LIMIT; Job zero/closed, wrapperexit2.
  Preserve it as a harness failure. No formal source or timeout changed.
  The corrected diagnostic must use the existing long benchmark owner plus
  a finite diagnostic deadline, O4.1/watchdog/measurement lock and actual exits.
  Add out-of-band call-return/signal stamps, keeping formal schemas and the
  2-second gate unchanged. Do not use a100-cycle success as formal acceptance
  or proof that the observed transient stall has been repaired.

## 2026-10-02 — bounded save runner; preflight stops before launch

- Added `studio/tests/replay/run_save_phase_diagnostic.py`: copied driver only,
  100 cycles, supplemental call-return/signal clocks, 180-second diagnostic
  deadline using the existing benchmark Job; production import retains20s.
  Fresh60-second O4.1/CPU observation, measurement lock, KeepAwake and watchdog
  remain required. Two focused pure tests passed, actual exit0; native validity
  is still unproven. Tracked driver, schemas, thresholds and formal timeouts unchanged.
- Command: `python -B -X utf8 studio/tests/replay/run_save_phase_diagnostic.py
  --run-id gt06-status-gap-save-diagnostic-20261002-02`, actual outer exit1.
  The underlying preflight failure is WATCHDOG_PERF_COUNTER_QUERY; the caller
  surfaced CAMPAIGN_PREFLIGHT_APP_INVENTORY because the failed snapshot contains
  null inventories. No source freeze/import/editor was reached; no CPU/RAM
  conclusion can be drawn from that missing sample.
- Fresh readonly snapshot succeeded, then run03 using the same CLI stopped
  during its minute before source freeze/import/editor, actual outer exit1.
  Five samples at20:22:58–20:23:23: available5.65GiB to3.19GiB,
  final commit80.31%; failure CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT. No cleanup errors;
  no owned Job was created. Preserve both run directories, do not resume them.
- Conservative O3 accounting uses all three IDs01–03, including the two
  prelaunch stops: no fourth retry without a new reviewed direction. Options:
  retain the instrumentation for a later resource-stable window after review;
  inspect the pinned save/preview path statically for a distinct hypothesis;
  continue AUTH-05 fixture work in O2 when its own fresh preflight passes.
  Neither successful preflight nor these stops repairs formal14 or permits formal15.
- Formal14 closeout archive: `studio/.local/reviews/gt06-formal14-closeout-20261002/raw.zip`,
  21,938,945 bytes, SHA256 `2b9d0cba0c397440d490f68b08c0b53ab5d6c741efdfa17c5480849f580d044a`.
  Original raw, file manifest and terminal receipts remain alongside it.

## 2026-10-02 — pinned save-path review and diagnostic identity

- Read-only code review (not an acceptance critic) identified a distinct preview
  hypothesis: the pinned preview wrapper performs viewport image readback, image
  processing and cached PNG output before calling the shared scene-save function.
  Disabling preview changes this workload; it is not an approved formal fix and
  does not prove preview/GPU/disk caused formal14. Sources: [preview implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L2255-L2338)
  and [preview switch](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.h#L981-L987).
- Preview progress can run a nested main-loop iteration. Therefore a heartbeat
  inside the save interval does not establish that the API returned. scene_saved
  is emitted before external-resource saving; direct post-signal progress pumping
  was not found. Callback reentrancy remains possible, not observed in formal14.
  [Progress pump](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/gui/progress_dialog.cpp#L148-L153),
  [save ordering](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L2518-L2559).
- Supplemental return markers now retain batch/cycle/start values captured before
  the call and record live identity separately. The parser rejects identity drift
  instead of joining a return to a different cycle. Three focused pure tests passed,
  actual exit0. No additional native run, production API change or gate change.
- Next reviewed diagnostic option: matched disposable preview-on/off variants,
  sequential100 cycles each with180s diagnostic deadlines, fresh O4.1/CPU minute,
  source binding and unchanged signal/hash/reload/actual-exit checks. This is a new
  hypothesis, not a fourth blind retry. save_scene_as returns void: never fabricate
  Error.OK for that variant. Cost roughly several minutes if admission passes;
  risks include cache/order and transient-stall confounding. Even a faster short
  variant does not establish repair or authorize formal15 without a further review.
- Alternative: retain the current instrumentation for a later stable resource
  window; cost unknown waiting time and it may not reproduce a transient. Meanwhile
  continue O2 work. No fourth run has been launched; old raw and verdicts unchanged.

## 2026-10-02 — formal13 pre-dispatch failure and launcher repair

- Formal13's fresh dry-run and arm preflight passed, but the launcher failed at
  18:31:03 Asia/Saigon in `prepare`: `Get-FileHash` was unavailable in that
  PowerShell process. `launcher-failure.json` records `run_invoked=false`;
  no campaign batches or new INFRA_ABORT budget were consumed. Preserve
  `.local/formal13-arm-20261002/` and
  `studio/.local/reviews/gt06-o4-formal-13-supervisor/`; do not reuse the ID.
- The command's absence is observed; its environment/module cause is not yet
  established. `Hash-File` now streams the file through .NET SHA256, retains
  literal-path validation, and disposes both stream and algorithm in `finally`.
  The SHA256 contract, gates, profile and timeouts are unchanged.
- A Windows PowerShell regression shadows `Get-FileHash` with a failing stub,
  checks a binary file with brackets in its path against Python SHA256, checks
  missing-file rejection and verifies stream release. It failed before the
  repair; `python -B -m unittest studio.tests.replay.test_campaign_task` then
  passed all 8 tests with actual exit 0. This proves the repaired hash boundary,
  not formal acceptance. Next arm must use the Windows one-shot registrar,
  fresh source binding and successful dry-run, rather than a tool session.

## 2026-10-02 — formal11 dispatch

- New campaign `gt06-o4-formal-11` was prepared from source closure
  `4ad0786bde478b1015011d0e00a0625f2aac5eb9f823f311b089954ed42b8ecd`, profile
  `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`, and the
  unchanged v6 gates/timeouts. Arm root is
  `studio/.local/formal11-arm-20261002/`; the successful dry-run is recorded
  there with a 60-second O4.1/CPU observation.
- Dispatch at 16:21 Asia/Saigon returned scheduler exit0 and created the
  supervisor output directory `studio/.local/reviews/gt06-o4-formal-11-supervisor/`.
  This is dispatch evidence only: formal acceptance remains false until both
  pairs finish with actual child/editor exits, cleanup, watchdog and dataset
  checks. Do not infer PASS from the scheduler banner or a partial prefix.

## 2026-10-02 — formal11 terminal harness failure

- The first pair launch observation completed 60.422 seconds with 13 samples and
  was bound to the fresh source hash. CPU intervals varied above and below95%
  (max100%, mean95.626%), so this record is not a sustained external-CPU
  abort. No pair reached 35 batches.
- After three batches the campaign watchdog raised `WATCHDOG_PERF_COUNTER_QUERY`
  while reading a host process counter. `parent-failure.json` classifies the
  run `HARNESS_FAIL`, with `owned_tree_zero=true` and `owner_closed=true`;
  supervisor return code is1 and says an actual natural child exit was not
  observed. This is neither product PASS nor product FAIL.
- The arm terminal snapshot had state3 and no instances but
  `last_task_result=1`; it is scheduler closeout only, not success evidence.
  Raw failure, launch observation and watchdog error remain under
  `studio/.local/reviews/gt06-o4-formal-11/` and its supervisor directory.
- After preserving `task-registered.xml`, the registration receipt and
  `arm-task-closeout.json`, the exact arm task was removed. Do not resume
  formal11, formal01–10 or S258. Review and repair the PerfCounter failure
  boundary with a reproducer before any new formal ID; do not retry blindly or
  lower O1–O4.

## 2026-10-02 — bounded PerfCounter repair and diagnostic

- Commit `7cfcc2d22c1f879989ef7b79a5877860f13607e2` keeps the absolute
  PerfProc query budget at8 seconds but divides it across the two permitted
  attempts. A stalled first query can no longer consume the whole budget and
  silently skip the bounded retry; unknown, malformed and late samples still
  fail closed and no O1/O4 threshold or campaign timeout changed.
- Focused regression suite `python -m unittest
  studio.tests.replay.test_benchmark_environment` passed52/52 with actual
  exit0. A host-only diagnostic invoked the fallback for the three observed
  WSL/Docker protected PIDs10 times; all10 returned all3 counters, actual exit0,
  with no Godot/Blender/Docker dispatch. Raw result and hash are under
  `studio/.local/reviews/gt06-perfcounter-repair-20261002-01/`.
- These checks cover the bounded retry logic and host counter reads; they do
  not reproduce the complete formal11 failure under load or prove its root
  cause. They do not turn formal11 into a pair or prove a product result. Before a new formal ID,
  freeze the new source closure, run a fresh O4.1 preflight and one-minute CPU
  observation for each pair, and verify the machine-on window and remaining
  INFRA budget. Do not retry formal11 blindly or lower any gate.

## 2026-10-02 — formal12 dry-run resource hold

- A new closure was prepared after the PerfCounter repair for
  `gt06-o4-formal-12`; no arm task or campaign was registered. The fresh dry-run
  verified source/profile, lock absence, scheduler idle and budget, but failed
  the O4.1 CPU observation with `OBSERVATION_EXTERNAL_CPU_PRESSURE`.
- The 60-second samples measured total machine CPU mean97.13% and max99.84% across12
  intervals. The stored observation does not attribute that load to a process outside
  the campaign Job, so it is not evidence of an external-CPU watchdog trigger. At the
  end, available memory was10.58 GiB and commit58.12%; the dry-run was blocked by
  the CPU observation, not by a RAM/commit gate failure. Raw
  samples and the decision remain under `studio/.local/formal12-arm-20261002/`.
- No engine, Docker or formal workload was started. Wait for a naturally quiet
  host, then perform one fresh dry-run; dispatch only if all O4.1/CPU checks
  pass. Do not close user applications automatically, lower thresholds or
  reuse this blocked dry-run as a formal receipt.

## 2026-10-02 — post-375947ee gate state

- Commit `375947ee` implements the O7.3c per-pair launch observation: each
  fresh pair now records a bound 60-second sample stream, replays O4.1/CPU
  policy, rechecks source and Stop before launch, and verifies freshness against
  the first watchdog sample. Focused launcher/campaign tests remain green
  (107 campaign tests and 11 arm/registrar tests, exit 0); no engine or formal
  campaign was run by this repair.
- A read-only host snapshot at `2026-10-02T07:52:37.9515200Z` showed 6.482 GiB
  available, total commit 79.661%, and total CPU 7.016%; this is one snapshot,
  not the required O4.1 60-second preflight. No campaign is live and no new
  formal ID was dispatched.
- The next formal requires an owner-confirmed machine-on window of at least
  four hours, a fresh source/profile freeze after `375947ee`, a new O4.1
  preflight plus one-minute CPU observation before each pair, and an unused
  daily INFRA budget. The one-minute observation must record process attribution
  separately from total CPU; total CPU alone cannot be labelled external pressure.
  Do not resume formal01–10 or S258, and do not lower O1–O4 thresholds/timeouts.

## 2026-10-02 — O4.1 read-only probe blocked

- Read-only probe `gt06-o8-preflight-20261002-01` bound the fresh source closure
  `4ad0786bde478b1015011d0e00a0625f2aac5eb9f823f311b089954ed42b8ecd` and
  profile v6. It stopped after the second sample with
  `CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT`: available memory stayed above 6.4 GiB,
  but total commit moved from 84.738547% to 85.02%, crossing the O4.1 `≤85%`
  launch gate. No foreign engine was present and no campaign/engine was started;
  this probe is not an INFRA_ABORT attempt. Raw samples remain under `.local/`.

## 2026-10-02 — O2 bounded-inventory milestone

- O2 branch `codex/o2-authoring-contract` commit `b4307012` replaces the
  executor's Docker admission inventory call with the bounded named-pipe
  request. It keeps exact `hh.gt03.executor` ownership, includes all container
  states, uses one five-second deadline, and fails closed without a CLI
  fallback. The focused pure suite is recorded as 71 tests, exit 0; runtime
  closure is 25 files, SHA256
  `f9e295de500888e4c1d3f721d2675e3dacaa96af7c4cec641b5eeac949284a91`.
- This is still `AUTHORITY=0`: no native confirmation was run because the host
  was over the O4.1 resource threshold, and the branch remains unmerged until
  GT06 is accepted. The earlier `o2-publication-20261002-03` timeout remains
  historical and is not replaced by this static proof.

## 2026-10-02 — per-pair launch guard repair

- `run_benchmark_campaign.py` now records a new immutable `environment-launch-samples.jsonl`
  and `launch-observation.json` for every fresh pair. Each record binds run/source/campaign hashes,
  recomputes O4.1 policy and CPU intervals from the raw samples, requires at least60 seconds with
  sample gaps within the existing cadence, rejects a process outside the campaign Job at >=50% CPU
  for60 seconds, pressure, sleep,
  source drift or Stop, and checks freshness against the first run watchdog sample. The pair is
  launched only after the observation and source/Stop recheck; old captures remain on their frozen
  verifier and cannot be rebound.
- Tests: launcher/registrar 11 tests exit0; campaign/environment/Stop/launch tests 107 exit0.
  No engine, Docker or formal campaign was run. This is harness evidence; it does not turn formal09
  or formal10 into accepted pairs. The next fresh formal must mint a new closure after this source
  change and pass O4.1 before each pair.

## 2026-10-02 — formal10 terminal review and arm repair

- `gt06-o4-formal-10` dispatched13:11:17 Asia/Saigon, terminal13:35:47; pair0 has20/35 batch captures.
  Raw parent verdict remains PRODUCT_FAIL / CAMPAIGN_WATCHDOG_COMMIT_PRESSURE. No second pair.
- Offline replay of288 watchdog samples reproduces the sole trigger at index287: total commit
  56,270,299,136 / 61,064,339,456 bytes =92.1492%; owned private902,148,096 bytes. Removing all
  owned private would yield90.6718%, so current conservative product hold is correct. It does not
  prove a causal leak. In the last interval total commit grew989,892,608 bytes while owned private
  fell28,672 bytes; this indicates an external/unobserved contribution, not sufficient attribution
  to reclassify the run. Keep O1/O4 unchanged.
- Quiescent partial prefix uses O1 baseline median batches2–4 and max batches5–19: host private
  103.4943%, editor100.5761%; host handles209, editor max564 versus baseline558; status-gap max
  host595.6511ms/native989.379ms. No batches20–34 means no late trend or whole-pair PASS.
  A transient host-private sample206,684,160 bytes is undiagnosed; do not hide it with quiescent data
  or infer retained leakage from a single peak. All120 capture refs and58 source files hash-match.
- Outer host Job cleanup records zero/closed, retained wrapper handle=false and wrapper exit2.
  Child actual exit and editor target-exit/cleanup receipts are absent because the parent watchdog
  hard-stopped the Job. This cannot be reported as natural exit0 or complete per-role proof.
  After-snapshot inventory has an unverified editor row which may be stale; it does not prove a
  live process leak. Scheduler result1/instances0 and no current engines were captured at14:01.
- Supplemental: `studio/.local/formal10-offline-audit-20261002/supplemental.json`, SHA256
  `82ca90a472e57fc4f92319c30296531faeed29af78c7908dd58b9bb0aeebc00a`; script SHA256
  `3a4b9264e0a972aa05e69d0e9b8f339cd43f8a6fb6bc34cf40eff170c86f4ed4`.
  Repro from tools root: `python -B studio/.local/formal10-offline-audit-20261002/offline_audit.py`.
  This is supplemental diagnostic evidence, not a signed critic or an acceptance package.
- Arm helper had NameError CAMPAIGN immediately after successful dispatch. Campaign ownership and
  its own KeepAwake continued independently. Repair uses request.campaign_id in status polling,
  validates gates before BEFORE_WINDOW, and requires a matching successful dry-run receipt before
  run/registration. Registrar checks exact task name and retains requested/readback XML.11 focused
  tests exit0 (mock dispatch plus real PowerShell ValidateOnly; no campaign or task registration).
- Historical procedural gaps retained: no recorded formal10 dry-run; formal09 arm was removed
  without prior XML export. Formal10 task XML/status are now in `.local/formal10-task-closeout-20261002`.
  Neither gap is retroactively repaired by today's tests. No formal11 is armed/dispatched.
- Next repair before another formal: the campaign currently records one fresh snapshot at each
  pair launch, while the arm observes CPU for a minute only before campaign dispatch. O7.3c asks
  for a minute before each pair; close this enforcement/evidence gap. Review abort observations
  without substituting killed exits for exit0. Then use a confirmed quiet machine-on window and
  fresh source/profile freeze; no gate/timeout relaxation and no user-app termination.

## 2026-10-02 — gt06-o4-formal-09 closeout

- Dispatch: `HHStudio.GT06.gt06-o4-formal-09`, one scheduler start at 10:43:10 Asia/Saigon;
  formal source closure `eaf377f8960303083d81f92e446401518ce2b80b38f405636aa43d9725f9c85b`
  (58 files), profile v6 `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`.
- Pair 0: 35/35 batches, child/host/editor actual exit `0`, Job/tree/handle cleanup verified,
  no watchdog latch; run summary status `PASS`, maximum status gap `1295.624 ms`, raw summary
  `c18ea56c92a6f1c7dcd3da2738618ae5a2b0de1ed968304cd6507bd82b2a2474`. This is one pair only;
  it does not grant GT06 acceptance.
- Supplemental offline `verify_run_capture` on02-10 rehashed all410 artifacts and verified35 batches,
  actual exits/Job/tree/handle/watchdog with the unchanged live source. Receipt:
  `.local/formal09-offline-closeout-20261002/verification.json`. This validates the existing run
  capture, not the per-pair CPU-minute omission identified above or complete GT06 acceptance.
- Pair 1: no batch started. Fresh preflight at `2026-10-02T04:18:53Z` recorded available
  memory `3667136512` bytes (3.415 GiB), commit `86.7199556%`, no foreign engines; classification
  `INFRA_ABORT` with `CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT`. Raw `run-01-attempt-01` is retained.
- Campaign is terminal with zero accepted formal pairs. The arm repair task was removed only after
  scheduler terminal/zero instances; arm receipts remain under `.local/formal09-arm-20261002-repair01`.
  Daily O1.7 INFRA budget consumed: `1/2` on 2026-10-02. Do not resume formal09 or S258; a new ID
  may be considered only after fresh source freeze, O4.1 preflight and one-minute CPU observation.
- Historical formal10 arm (now terminal; see review above): one-shot task `HHStudio.GT06.arm-formal10-20261002`, window 13:00–17:00 Asia/Saigon,
  request bound to the same freshly computed 58-file closure and profile v6. It must dispatch at most
  one new ID and records no-dispatch when commit/RAM/CPU or budget is not valid.

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

## 2026-10-02 — Preview A/B direction, preregistered before native launch

- Distinct hypothesis from the pinned review above: preview readback/PNG work
  may dominate the synchronous scene-save call. This starts a reviewed A/B
  direction under O3, not a fourth repeat of the prior resource-blocked run.
- Run stock then off, each fresh disposable project and100 cycles with the
  same source, fresh60-second preflight,20-second import and180-second editor
  diagnostic deadline. Planned IDs: gt06-preview-stock-20261002-01 and
  gt06-preview-off-20261002-01. Stop and review if the first run fails to reach
  its intended boundary; no automatic rerun. Direction budget:3 attempts/4h.
- Stock preserves save_scene() Error checking. Off calls save_scene_as(SCENE,
  false), whose return is void; record null, retain signal/disk/semantic
  readback and reload. Four focused pure tests passed before dispatch, exit0.
  Variant is bound in copied driver bytes, freeze, markers and offline joins.
- Compare call/signal/readback and heartbeat timings. Fixed order, independent
  caches and transient host load limit causal inference. A fast off run is
  diagnostic only; it neither repairs formal14 nor changes the formal workload.

## 2026-10-02 — Preview A/B completed; transient stall remains unproven

- `gt06-preview-stock-20261002-01` (20:55–20:57):100/100 cycles, outer/import/
  editor actual exit0; source unchanged, watchdog verified, Jobs zero/closed,
  process handles/probe released. Binding closure
  `29cf524478f0c43e95a97201afb28d9488120a635fedd3f6387186c4602b83d1`.
  Save call median/p95/max52.1935/66.398/297.444ms; total save
  60.8245/88.157/304.270ms. Native maximum status gap558.955ms.
- `gt06-preview-off-20261002-01` stopped before source freeze/import/editor:
  fresh minute fell from4.93 to3.67GiB available, commit77.178%, outerexit1
  CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT, no owned Job. Preserve raw unchanged.
  A later readonly snapshot recovered to7.02GiB/71.27%; then fresh ID02.
- `gt06-preview-off-20261002-02` (20:59–21:01):100/100, actual exits0 and same
  clean owned lifecycle. Binding closure
  `7944ad3315b1bd6ac35c6514cc9d5cd15c92e14ed87a062e40293642fdc3efdd`.
  Call median/p95/max22.050/31.114/60.429ms; total29.292/40.680/68.173ms;
  maximum status gap550.868ms. p95 above uses nearest-rank of100 values.
- Shared58 source files were byte-identical across stock/off; only copied
  variant/run binding differs. Final scenes differ only in generated root
  unique_id. Each variant independently passed100 signal/disk/semantic/reload
  checks; there was no call-identity drift. Original timing/raw kept intact.
- Both native runs failed to reproduce the5.078s formal14 gap. Preview-off
  lowers ordinary save cost in this sample, but order/cache/host load remain
  confounders and cannot explain the prior tail stall. Three IDs consumed this
  direction; do not run a fourth or promote off into formal merely to pass.
  Review actual managed save versus benchmark workload/reentrancy next; when
  evidence is insufficient, continue O2. Formal14 stays PRODUCT_FAIL.

- Read-only design review: production managed save uses checked PackedScene/
  ResourceSaver capture plus publication-owner validate/CAS/adopt/reload.
  The direct EditorInterface save in this benchmark is deliberately synthetic;
  removing preview would therefore change benchmark workload, not repair a
  production consumer. No actual reentrant phase drift was observed in A/B.
  Signal plus unchanged baseline alone is weak failed-save proof, but the full
  error-log/modal path has not been reproduced bypassing the verifier; do not
  present this static concern as an established false PASS or tail-stall cause.
- O3 direction closeout/options: (1) continue O2 now, no extra GT06 runtime;
  (2) a focused disposable failed-save negative, if pursued, tests proof strength
  only, not the5s stall; (3) no-preview needs an explicit reviewed workload/profile
  decision before any formal use. It must not inherit v6 comparability or change
  old verdicts. Selected now: option1, preserve formal source/timeouts/gates.

## 2026-10-02 — Offline correlation review after O2/native closeout

- Read-only review of formal14 `environment-launch-samples.jsonl` found 15
  samples over about 65 seconds, with aggregate CPU mean 17.38% and maximum
  26.98%. The samples contain UTC wall time but no monotonic binding to the
  benchmark phase clocks; they cannot be joined safely to the 1.324 s, 2.019 s
  or 5.130 s save bursts. Batch preview records are post-batch snapshots, not
  measurements during the save call.
- Existing call/scene-saved/readback timestamps remain the sufficient
  decomposition for a future reproduced stall. No CPU, memory, disk or
  scheduler cause is established, so no runtime latency patch, timeout change
  or formal15 dispatch is authorized by this review. Keep formal14 PRODUCT_FAIL
  and all raw evidence unchanged.

## 2026-10-03 — gt06-o4-formal-17 terminal observer failure

- Formal17 dispatched at 04:06:04 Asia/Saigon from source closure `cdcbdfad52fcec569b187f629d57a534a8d6a1be867d7189f7c7bb92e83fc392`, profile v6 `8a2e599c…`; O4.1 dry-run and launch observation were recorded. The campaign stopped after warmup batches `0..2` at watchdog sample `61` with `CAMPAIGN_WATCHDOG_OBSERVER_ERROR` / `WATCHDOG_DOCKER_INVENTORY`; the Docker pipe diagnostic was `timeout`, attempt `1`, elapsed `2.0 s`.
- This is a harness/observer failure, not an INFRA_ABORT, product verdict, O1 pair or acceptance. Actual child/editor natural exits were not observed; wrapper exit `2`, Scheduler closeout result `1`, owned Job/tree closed with zero active members and no retained handle. Raw evidence and `closeout-check.json` remain under `studio/.local/reviews/gt06-o4-formal-17/`; exact arm task `HHStudio.GT06.arm-formal17-20261003` is absent after terminal closeout.
- Review found the timeout was converted to a non-retryable error even when `OwnedPipe.close()` completed cleanly. Repair in the measured observer boundary marks only `PIPE_TIMEOUT` retryable under the same absolute two-second budget; malformed output, drain-pending, other I/O errors and uncertain cleanup remain fail-closed. Focused Docker/environment/native-pipe suite: `87` tests, exit `0`. Because formal17 consumed the full two-second deadline, this repair does not claim to fix that exact full-budget stall; the early-timeout retry and failed-close guard are now covered separately.
- Do not resume formal01–17/S258 or dispatch formal18 blindly. First review this repair, freeze a fresh source/profile closure, pass O4.1 plus the one-minute CPU observation in a valid window, then use a new campaign ID. GT06 remains incomplete; O2 stays separate and unmerged.

## 2026-10-03 — gt06-o4-formal-19 terminal observer failure

- Formal19 was dispatched at 04:44:05 Asia/Saigon from fresh source closure `8512eb3394ee9528c80412ac5578b2f47f14ca500a72017f8142dd3fb19e907f`, profile v6 `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`, after the sliced two-second Docker observer repair and a passing O4.1 dry-run. It produced warmup batch `0`, then stopped at watchdog sample `48` with `CAMPAIGN_WATCHDOG_OBSERVER_ERROR` / `WATCHDOG_DOCKER_INVENTORY`; observer attempt `2` elapsed `2.016 s` and timed out.
- This is a harness/observer failure, not an INFRA_ABORT, product verdict, O1 pair or acceptance. Child/editor natural exits were not observed; wrapper exit was `2`, Scheduler closeout result was `1`, and the owned Job/tree closed with zero active members and no retained handle. The exact arm task `HHStudio.GT06.arm-formal19-20261003` was removed after terminal closeout. Raw evidence and `closeout-check.json` remain under `studio/.local/reviews/gt06-o4-formal-19/`.
- The preceding repair commit `d04266e8` split the same absolute two-second observer deadline across two attempts and the focused Docker/environment/native-pipe suite remained green (`87` tests, exit `0`). A separate direct observer probe had also returned valid inventories, so the formal failure demonstrates that the intermittent full-deadline stall is still unproven; it does not establish a source leak or a causal fix.
- Do not resume formal01–19/S258 or dispatch formal20 blindly. Review the full-deadline observer boundary and identify a distinct, reproduced repair or a clean-environment diagnostic window first; then freeze a new source/profile closure and pass O4.1 plus the one-minute CPU observation before any new campaign ID. GT06 remains incomplete with zero accepted pairs; O2 remains separate and unmerged.

### Review after formal19 closeout — cleanup reserve repair (pending fresh closure)

- Formal19’s `2.016 s` terminal observation is a real deadline-accounting gap: `running_containers()` gave the second pipe operation a deadline at `t0+2 s`, while `_io` and `OwnedPipe.close()` can each consume a bounded `250 ms` drain when completion is uncertain. The extra time must not be clamped or treated as valid inventory.
- The repair reserves `0.6 s` for the worst-case two-stage cleanup inside the unchanged absolute `2 s` budget, giving one operation a `1.4 s` cutoff. A quick transient error may retry against that same cutoff; a full timeout cannot start a late second read. A focused mocked timeout-plus-`250 ms` cleanup test proves the recorded elapsed time remains ≤ `2 s`; the environment/Docker/native-pipe suite now has `88` tests, exit `0`. The O1/O4 thresholds and timeout remain unchanged.
- This is a source-level repair for the observed boundary, not acceptance evidence. Freeze a new closure and run a fresh O4.1/CPU-minute check before any next campaign; do not dispatch formal20 from the old closure or raw.

## 2026-10-03 — gt06-o4-formal-21 terminal status-gap product failure

- Formal21 dispatched at 05:11:06 Asia/Saigon from fresh source closure `01c735149811d4d49f92e478c69386d8db6edc6e0ffbefa19eb0e46c883b39ed`, profile v6 `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`, after the cleanup-deadline repair and a passing O4.1 dry-run. It reached one warmup batch and stopped in `joint_observation` with `CAMPAIGN_STATUS_GAP`; the authoritative sample preview reports `max_status_gap_ms=2766.6174`, above the unchanged O1 limit of `2000 ms`. The joint barrier receipt for the same batch was `650.59 ms`, so the phase/timestamp discrepancy must be reviewed from raw evidence rather than averaged or ignored.
- This is a `PRODUCT_FAIL` under the O1 status-gap rule, not an INFRA_ABORT and not a Docker watchdog failure. Host wrapper actual exit was `1`; import host exit was `0`; the editor target natural exit was not recorded. Owned Job/tree closed with zero active members and no retained handles. The exact arm task `HHStudio.GT06.arm-formal21-20261003` was removed after terminal closeout; raw evidence and `closeout-check.json` remain under `studio/.local/reviews/gt06-o4-formal-21/`.
- The result does not prove a memory leak or explain formal14’s save tail. Preserve the verdict and raw files. Review the batch-0 status-gap phase, editor/host monotonic timestamps and receipt-generation boundary before any new formal ID; do not resume formal01–21/S258 or dispatch formal22 blindly. GT06 remains incomplete with zero accepted pairs; O2 remains separate and unmerged.

### Offline scope binding after formal21

- The apparent `2766.6174 ms` versus `650.59 ms` discrepancy is a scope difference,
  not a reason to average or discard the failure. In `run-00-attempt-01`,
  `command-00.json` has a real `2766618 us` gap between adjacent
  `host_response_mono_us` samples (indices 3632→3633); its
  `status_gap_scope` is the host command-lane response progress. The native
  `batch-00.json`/joint barrier reports `650.59 ms` for the editor heartbeat
  lane only. `assemble_sample()` takes the maximum of command, native and
  barrier/start-permit gaps, so the authoritative sample value `2766.6174 ms`
  correctly violates O1.5. This is a product status-gap failure, not an
  evidence merge error or Docker watchdog event.
- The gap has no command receipt timestamp inside it and no monotonic CPU
  binding that proves a cause. Keep the raw verdict, review the host-lane
  stall boundary/reproducer before a new formal ID, and do not lower O1 or
  dispatch formal22 blindly. The next source review must also close the O9.1
  requirement that in-run CPU sampling avoid the remaining PowerShell/PerfProc
  fallback; the current implementation is not yet evidence that O9.1a is done.
- The gap is localized to admitted command `.153` (row ordinal `769`): its
  same-ID lookup attempts remain `QUEUED` for roughly 2.766 s before the final
  `READBACK_CONFIRMED`; no transport failure is recorded. The retained HTTP
  ring starts after this interval, so it cannot prove whether journal/queue
  contention caused the stall. A future diagnostic must persist bounded
  per-command phase timestamps or reproduce from the journal seed before any
  source patch or formal retry.

### O9.1a repair after formal21 — kernel-only process counters

- Commit `bb35bdc3` replaces the in-measure process-counter fallback with the
  Windows kernel `NtQuerySystemInformation(SystemProcessInformation=5)` API.
  The query grows its buffer only on `STATUS_INFO_LENGTH_MISMATCH`, enforces a
  bounded 64 MiB allocation, validates the x64 record size/offset chain and
  returns a fail-closed unknown result for a missing target PID. PowerShell and
  PerfProc are not used by the measured watchdog path; the compatibility
  `perf_process_times` name remains for callers and tests.
- The focused environment suite passed `53/53`, exit `0`, after the repair;
  an additional read-only host probe on the live Windows host returned real
  PID counters with `cpu_source=NtQuerySystemInformation`, and `py_compile`
  passed. This validates the query path only; it is not a formal pair and does
  not explain the formal21 command-lane stall.
- O9.1a is therefore source-repaired, but the required 30-minute
  watchdog-only soak, distinct command-gap reproducer/review and fresh O4.1
  freeze are still open. Do not dispatch formal22 or change O1/O4 thresholds
  until those gates are complete.

### O9.1b repair — bounded Docker observation and executor lock fence

- Commit `7495eea6` keeps Docker out of the mandatory in-measure sample path:
  `native_snapshot()` takes a deferred inventory for watchdog rows, while
  `Watchdog` polls at most once per 60 seconds. A pipe timeout, malformed
  response or other Docker read error is recorded as `UNKNOWN` and does not
  stop the CPU/RAM/commit/sleep stream; a previously observed studio-owned
  container remains conservatively visible until a successful poll clears it.
  Preflight still uses the strict bounded pipe and fails closed before a pair.
- The same repair fences `measure-window.lock` immediately before Docker
  `create` and `start` in the main executor. O2 carries the equivalent fence
  in commit `4be9af68`; its focused executor/asset/dependency suite passed
  `42` tests, exit `0`. Pure cadence/error and executor lifecycle tests pass;
  no Docker/Godot run was started by this source repair.
- Current verifier mode requires each new formal watchdog row to carry
  `KNOWN`, `CACHED` or `UNKNOWN` Docker status plus a bounded error object when
  unknown. Historical raw remains readable under the compatibility default.
  O9.1b still needs the 30-minute watchdog-only soak and its independent
  duration/source/lifecycle verification before a new formal freeze.

### Offline formal21 command-gap review — diagnostic only

- `studio/tests/replay/review_formal21_gap.py` reads the preserved
  `command-00.json` without starting an engine or changing the measured source.
  Its focused unit suite passed 3/3, and the generated review/replay under
  `studio/.local/reviews/gt06-formal21-gap-review-20261003-01/` binds the raw
  SHA-256 `4a4eb4136d1d0b3579f5b4494051eab154709a0510252a267bc1f6990d29a55d`.
- The largest monotonic lookup gap is `2766618 us` between adjacent QUEUED
  attempts of admitted command `.153`; both transport-failure fields are null.
  The result explicitly sets `formal_acceptance=false` and
  `root_cause_proven=false`. It confirms a reproducible evidence boundary,
  not a repair or permission to dispatch formal22.
- The in-memory phase replay binds the same raw SHA and reproduces the same
  monotonic delta without sleeping or starting a process. It is a deterministic
  diagnostic replay, not a scheduler/queue reproduction and not acceptance
  evidence.

### Controlled host command-gap reproducer — diagnostic only

- `studio/tests/replay/run_command_gap_reproducer.py` ran twice with actual
  process exit `0`; the retained fresh result is
  `gt06-gap-repro-20261003-02` under
  `studio/.local/reviews/gt06-command-gap-reproducer-20261003-02/`. It used
  the real loopback `CommandProducer` fixture, injected one bounded `2.5 s`
  delay at admitted lookup `.0`, and started neither Godot nor Docker. Its
  complete source closure is
  `10485c949411b5672631cc7a8952989ee3c6dad32ff728708b6f1d6c42c91188`.
- The controlled run recorded `max_status_gap_ms=2509.9916` and retained
  phase/journal timing, with no dropped commands, no transport failure and all
  effects reconciled. It demonstrates that the unchanged 2-second host gate
  observes a delayed lookup; it does not reproduce the formal21 scheduler,
  prove a natural root cause, or permit formal22. A fresh full O9 watchdog soak
  remains required before any new formal freeze.

### O9 watchdog soak closeout — valid run

- `gt06-o9-watchdog-soak-20261003-08` used the post-repair source closure
  `22db76103738d7cf4327f94fcd234d882610ed14831e432e9e93debc946a55ec` and
  ran outside a formal window with `godot_started=false` and
  `docker_create_started=false`. Its actual process exit is `0`, elapsed
  coverage is exactly `1800 s`, the stream has `354` data samples, and
  `soak-result.json` records `verified_watchdog=true`.
- Docker evidence is bounded and explicit: `KNOWN=30`, `CACHED=324`, with no
  `UNKNOWN` or watchdog stop latch. The raw stream, context, result and source
  manifest remain under `studio/.local/reviews/gt06-o9-watchdog-soak-20261003-08/`.
  This closes the O9.1 watchdog-soak DoD, but it is not a formal pair and does
  not change GT06 acceptance.

### O9 soak closure repair — incomplete attempts retained

- The first detached soak attempts were stopped after partial samples and had
  no `soak-result.json`; one setup attempt only reported `SOAK_OUTPUT_EXISTS`.
  They are invalid DoD evidence and remain untouched under `.local`.
- Audit found the runner's four-file manifest omitted the campaign's imported
  dependency closure, including `benchmark_docker_inventory.py`. Commit
  `ccb6792c` now reuses `campaign.source_files()` and adds the soak entrypoint;
  the computed closure contains 59 files. Focused O9/environment/executor and
  soak-manifest tests pass (80/80). A fresh soak with this closure is required.
