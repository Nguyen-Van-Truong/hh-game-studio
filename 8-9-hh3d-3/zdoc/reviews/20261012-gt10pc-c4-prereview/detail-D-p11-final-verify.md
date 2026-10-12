# P11 release-soak pre-review (read-only)

Audit date: 2026-10-12. Repo HEAD `d9a13d22`. Matrix file at HEAD commit `36d5322216cdb4885deb4f2519022586345a6525` (`GT10PC: enable final matrix and deep verify`, 2026-10-12 07:19:48 +0700). HEAD blob sha256 of `8-9-hh3d-3/studio/tests/conformance/run_gt10pc_matrix.py` is `cb65b63272b282d48167fbdc93a258702aef38bc6308db75b6767cb5b9a0f211` (63105 bytes). Working tree of that file is uncommitted sha256 `e89c6f837a191ebac3ef1c5d7b87c7abc40b93904999f46e4e5061af7cabc57a` (59505 bytes). Untracked: `8-9-hh3d-3/studio/tests/conformance/gt10pc_matrix_verify.py`.

No Godot, Blender, matrix, task, or benchmark was launched. Line numbers for HEAD are from `git show HEAD:8-9-hh3d-3/studio/tests/conformance/run_gt10pc_matrix.py`. Line numbers for WIP are the working tree.

---

## 1. Exact P11 requirement

Release soak, not the rehearsal shortcut.

- Plan P11 (`8-9-hh3d-3/zdoc/8-9-godot-blender-agent-studio-plan.txt` lines 273–276): “Release soak 10×35 theo O1/O4.1 trên đúng hash release (khoảng 6 giờ máy yên; diễn tập chỉ một vòng ngắn); mỗi vòng là run Godot thật có receipt, không phải vòng chép file.” Final starts in the evening via Scheduled Task and holds the O5.6 measure lock (lines 275–276). DoD restates “10 fresh pair × 35 batch theo OWNER O1 trên source release; môi trường theo O4.1, được chia nhiều cửa sổ chạy trên cùng hash” (lines 1458–1459). Same split sentence at line 523.
- O1.6 (lines 393–394): “GT-06 benchmark = 2 fresh host/editor pair × 35 batch. Full 10 pair × 35 batch là release soak trong DoD GT-10, chạy trên source release, chia được nhiều cửa sổ trên cùng hash (O4.6).” After GT-06 acceptance, O1 applies only to the GT-10 release soak, not to diagnostic runs (lines 410–411).
- Work per batch, O1.5 (lines 390–392), frozen in the accepted profile `gt06-tools-ux-o5-v6` (`8-9-hh3d-3/studio/tests/replay/benchmark_profile.py` lines 63–69, 102–111): each pair is 5 warmup + 30 measured batches = 35. Each batch is 500 inspect + 300 rejected + 200 admitted = **1000 commands**, plus **100 native cycles**. Same host PID and same editor PID for every batch of that pair (`PROCESS_RESTART`, `benchmark_profile.py` line 341). No duplicate or lost effect: every admitted effect count must be exactly 1 (`DUPLICATE_OR_LOST_EFFECT`, lines 353–355). `dropped_commands` must be 0 (line 385).
- Status gap: ≤ 2000 ms in every batch, including the 5 warmup batches (plan lines 390–392 and O4.2 at lines 482–483). Profile field `max_status_gap_ms = 2000` (`benchmark_profile.py` line 73).
- Memory gate O1.4 (plan lines 387–389): private commit, same API as the benchmark observer: max(batch 5–34) ≤ 110% baseline and max(batch 20–34) ≤ 105% × max(batch 5–19). RSS is recorded and is not an automatic gate. Counter tolerances are O1.3 (lines 381–386), not repeated here.
- Exit and ownership, O1.5 (lines 390–392): actual exit 0, owned tree 0, retained owned handles 0, Job zero/closed. The accepted campaign verifier requires host and editor `actual_process_exit.exit_code == 0`, `natural_tree_exit`, `job.closed`, `job.zero_observed`, and `job` not tainted (`run_benchmark_campaign.py` lines 1181–1188).
- Environment O4.1 (plan lines 467–478): before each pair, RAM available ≥ 4 GiB, commit ≤ 85%, no `godot*`/`blender*` outside the campaign Job, keep-awake, inventory before/after. Watchdog (≤ 10 s) may Stop + `INFRA_ABORT` (O1.7, lines 395–398) on low RAM, high commit, foreign CPU, foreign engines, or sleep. Watchdog must not turn FAIL into PASS.
- Windows on the same hash are allowed (O1.6 line 394; line 523; lines 1458–1459). Rehearsal is explicitly one short real Godot iteration (lines 273–274; C2 at lines 203–204). Diagnostic runs are not the 10×35 gate (lines 410–411).

Arithmetic of a full soak: 10 pairs × 35 batches = 350 batches. Measured batches exclude warmup: 10 × 30 = 300. Commands 300 × 1000 = 300000. Cycles 300 × 100 = 30000. Warmup is still gated for status gap (extra 10 × 5 = 50 batches, 50000 commands, 5000 cycles) and is not in the “measured_*” counters.

---

## 2. What c3e and p11a actually ran

Both are rehearsals of one diagnostic Godot cycle. Neither is 10×35 or 2×35.

### c3e — whole matrix, P11 short

Package: `8-9-hh3d-3/studio/.local/reviews/gt10pc-rehearsal-20261012-c3e/`
Task: `8-9-hh3d-3/studio/.local/reviews/gt10pc-rehearsal-20261012-c3e-task/`
Child raw: `8-9-hh3d-3/studio/.local/reviews/gt06-p11-short-318382fd/`

| Fact | Value | Where |
|---|---|---|
| Mode / status / authority | `REHEARSAL` / `REHEARSAL_PASS` / authority 0, acceptance false | `matrix.json` |
| Rows | P1–P11 | `rows_requested` |
| Matrix payload closure | `a90f378e10ecd6326e38b0cac39b5b4675ff4b71e3ecd2b5151cb3733d7e4f03` | `matrix.json` `source_closure_sha256` |
| Task closure (different function) | `1301d0b2a8415d892738fa9fd640d9db1d3d490f1a48ed4b2a9aaed3a9e072be` | `c3e-task/request.json` |
| Runner bytes | `matrix_sha256` `cb65b632…a0f211` = HEAD blob above | `c3e-task/request.json` |
| Task exit | `returned_exit_code` 0, `actual_process_exit_observed` true, elapsed **1640.281 s** (27 min 20 s) | `c3e-task/return.json` |
| Scheduler | task `\HHStudio.GT10PC.gt10pc-rehearsal-20261012-c3e`, `last_task_result` 0, start `2026-10-12T00:44:18.6413800Z` | `task-start.json`, `task-terminal.json` |
| P11 coverage | `one-real-Godot-cycle`, `full_benchmark` false, status `REHEARSAL_PASS` | `matrix.json` row P11 |
| P11 run id | `gt06-p11-short-318382fd` | same |
| Command | `python.exe -B …/tests/replay/run_native_benchmark.py --run-id gt06-p11-short-318382fd` | row P11 `child.command` |

Counts for P11 inside c3e:

- Formal pairs: **0**. Diagnostic profile is `batches: 1`, `cycles_per_batch: 1`, `warmup_batches: 0`, `host_integrated: false`, `full_benchmark: false` (`gt06-p11-short-318382fd/diagnostic-profile.json`; profile constants in `run_native_benchmark.py` lines 38–45).
- Batches: **1** (`project/benchmark/out/batch-00.json`, index 0, mode diagnostic). That batch has **1 cycle** with create/undo/save/reload, not 1000 host commands and not 100 cycles.
- Godot processes: **2**, sequential stages, not a measurement pair. Import PID **34644** exit 0. Editor PID **20344** exit 0.
- Python benchmark child (the matrix’s owned child, not Godot): target PID **40300**, exit 0. Child wall `finished_epoch - started_epoch` = 1791767494.5102441 − 1791767465.3712845 = **29.139 s**.

Host-recorded exits and PIDs (yes):

- Matrix child: `p11-short-child/p11-short-host.json` records `target_pid` 40300 and `exit_code` 0. Receipt `p11-short-receipt.json` repeats `target_pid`, `exit_code` 0, `wrapper_exit_code` 0, `tree_verified` true, `timed_out` false. This PID is the Python process.
- Import Godot: `gt06-p11-short-318382fd/import-host/process-exit.json` `{"pid": 34644, "exit_code": 0}` and `import-host/capture.json` `actual_process_exit` same PID/exit, `wrapper_exit_code` 0, `natural_tree_exit` true, `job.closed` true, `zero_observed` true, `handle_retained` false, `active_at_wrapper_exit` 0, elapsed 10.031 s.
- Editor Godot: `editor-host/process-exit.json` and `editor-host/capture.json` PID 20344 exit 0, job closed/zero/not retained, `active_at_wrapper_exit` 0, elapsed 15.454 s.
- Aggregated `capture.json` `actual_exits` matches those two PIDs and exits. `jobs.import` and `jobs.editor` are closed, `zero_observed` true, `handle_retained` false.

Task `stderr.txt` is 0 bytes. `stdout.txt` is 21597 bytes (not re-interpreted as the exit; the return receipt says the process exit was observed).

P1–P10 wall inside this package is about 1640.281 − 29.139 = **1611.14 s (26 min 51 s)**. The “about 27 min” figure is this whole-matrix task, which already includes the 29 s P11 child.

### p11a — focused P11 rehearsal

Package: `8-9-hh3d-3/studio/.local/reviews/gt10pc-rehearsal-20261012-p11a/`
Task: `8-9-hh3d-3/studio/.local/reviews/gt10pc-rehearsal-20261012-p11a-task/`
Child raw: `8-9-hh3d-3/studio/.local/reviews/gt06-p11-short-d0782023/`

| Fact | Value | Where |
|---|---|---|
| Mode / status | `REHEARSAL` / `REHEARSAL_PASS`, authority 0, acceptance false | `matrix.json` |
| Rows | P11 only | `rows_requested` |
| Matrix payload closure | `f8dfeda689e93327ca3c1deb441d8d84bbf8403037fb64e0c1a3e9d27d33ee51` | `matrix.json` |
| Task closure | `af50aca37a86b9314cd6f70346e66d0cbbd5bcb7e08cee6777f895bf2a671ee5` | `p11a-task/request.json` |
| Runner bytes | `matrix_sha256` `52001858fc17bdcaa40fbed4046b40252cfdffb1f936bca38cf8f2acfc707efb` | same |
| That blob | commit `3e45f4af52be61915832ae80bdb9339e03c1e084` (`GT10PC: bind shallow staging and rehearse P11 cycle`, 2026-10-12 06:15:34 +0700), **not HEAD** | git blob hash |
| Task exit | `returned_exit_code` 0, `actual_process_exit_observed` true, elapsed **33.0 s** | `return.json` |
| Scheduler | `\HHStudio.GT10PC.gt10pc-rehearsal-20261012-p11a`, `last_task_result` 0, start `2026-10-11T23:16:31.7539550Z` | `task-start.json`, `task-terminal.json` |
| P11 coverage | `one-real-Godot-cycle`, `full_benchmark` false | `matrix.json` row P11 |
| Command | `run_native_benchmark.py --run-id gt06-p11-short-d0782023` | row P11 `child.command` |

Counts: **0 formal pairs, 1 diagnostic batch, 1 cycle, 2 Godot processes**. Import PID **32440** exit 0. Editor PID **14132** exit 0. Python child PID **30220** exit 0. Child wall 1791760624.4220786 − 1791760600.404703 = **24.017 s**. The 33.0 s task elapsed includes artifact build around that child.

Host-recorded: yes, same layout as c3e.

- `p11a/p11-short-child/p11-short-host.json`: `target_pid` 30220, `exit_code` 0 (Python child).
- `gt06-p11-short-d0782023/import-host/process-exit.json` and `capture.json`: PID 32440, exit 0, job closed / zero / handle not retained, elapsed 8.016 s. **`active_at_wrapper_exit` is 1** (editor stage and the c3e import stage are 0). `active_before_cleanup` is 0 and `natural_tree_exit` is true. See MINOR below.
- `editor-host/process-exit.json` and `capture.json`: PID 14132, exit 0, job closed / zero / not retained, `active_at_wrapper_exit` 0, elapsed 11.813 s.

These rehearsals match the plan’s “one short iteration” sentence. They do not satisfy 10×35.

The task closure and the matrix closure differ on purpose. `run_gt10pc_task.py` lines 48–54 hash `{"payload": <matrix payload digest>, "publisher": sha256(gt10pc_signing.py)}`. `matrix.json` stores only the payload digest from `run_rehearsal` (`_payload_digest(_source_files(ROOT))`). They are not two measurements of one string.

---

## 3. HEAD final P11 vs WIP

The implementer’s claim is true for HEAD.

### HEAD final mode (`git show`, lines 238–314 and 721–723)

`run_rehearsal` calls `_p11_full_final(output)` only when `mode == 'FINAL'` (lines 721–723). That function:

- Builds one id `gt06-gt10pc-final-<8 hex>` and calls `campaign.run_campaign(campaign_id, campaign_root)` in-process (lines 247–251).
- Requires `frozen.run_count == profile.PROFILE.process_runs` and `batches_per_run == warmup + measured` (lines 270–271). The profile freezes `process_runs = 2`, `warmup_batches = 5`, `measured_batches = 30` (`benchmark_profile.py` lines 63–65 and the version tuple at line 102, which starts `…, 2, 5, 30, 500, 300, 200, 100, …`).
- Requires summary `measured_batches == 60`, `measured_commands == 60000`, `measured_cycles == 6000` (lines 280–283). That is 2 × 30 measured batches, 2 × 30 × 1000 commands, 2 × 30 × 100 cycles.
- Sets `coverage: 'formal-2x35'` and `full_benchmark: True` (lines 307–308).
- Verifier `_verify_p11_final_row` repeats `coverage == 'formal-2x35'` and `len(runs) == profile.PROFILE.process_runs` (lines 320 and 353).

`run_campaign`’s measurement-window label is the string `'GT06 formal 2x35'` (`run_benchmark_campaign.py` lines 1209–1215). Entry point is the in-process campaign, not five campaigns and not `run_native_benchmark.py` (that script is the rehearsal path, HEAD lines 151–161, same shape as WIP lines 131–142).

So HEAD final P11 is **one GT-06 campaign: 2 fresh pairs × 35 batches**. It is not 10×35.

Final mode cannot be narrowed with `--rows`: `parser.error("final must run the entire frozen matrix")` (HEAD lines 1023–1024). The scheduled-task supervisor repeats that (`run_gt10pc_task.py` lines 72–73, `GT10PC_FINAL_REQUIRES_ALL_ROWS`). One task process therefore runs P1–P11 together, and P11 is that single 2×35 campaign.

### WIP (uncommitted; not what c3e ran)

Working-tree `_p11_full_final` (lines 277–333) docstring: “Five clean frozen-v6 campaigns, each 2x35: 10 fresh pairs total.”

- Loop `for index in range(5)` (line 286). Each campaign id `gt06-g10a-<8 hex>`.
- Each campaign is a **new Python subprocess** of `tests/replay/run_benchmark_campaign.py --campaign-id <id>` (lines 218–221), `proc.wait(timeout=4 * 3600)` (line 234). Receipt schema `hh-gt10pc-p11-campaign-receipt-1` stores the subprocess pid and exit (lines 239–244).
- Each campaign must have `run_count == 2`, `batches_per_run == 35`, summary PASS, `measured_batches == 60`, `measured_commands == 60000`, `measured_cycles == 6000` (lines 296–301).
- Five campaigns: `pair_count` 10, `total_batches` 350, `measured_batches` 300, `measured_commands` 300000, `measured_cycles` 30000, `coverage` `formal-10x35` (lines 328–332).
- 5 × 2 runs × 2 roles = 20 (role, pid, process_start) identities, all distinct (lines 325–327).
- Still calls the accepted GT-06 profile and `summarize_dataset` / `validate_dataset`. It does not invent a 10-pair profile. `BenchmarkProfile.__post_init__` rejects any other `process_runs` (`benchmark_profile.py` lines 100–111).

WIP verifier that `--verify-only` actually calls is `gt10pc_matrix_verify._verify_p11_10x35` (via `verify_matrix`, wired at working-tree `run_gt10pc_matrix.py` lines 396–403 and 890–903). That function re-checks five campaigns, 20 identities, release-byte binding, and the 60/60000/6000 counters per campaign (`gt10pc_matrix_verify.py` lines 8–87).

Stale function still in the WIP runner: `_verify_p11_final_row` (lines 336–339) still requires `coverage == 'formal-2x35'` and a single `campaign` path. Nothing in the WIP tree calls it (only the definition matches). The live path is the new module. If a later edit calls the old function, a correct 10×35 row fails.

WIP is not committed. c3e’s `matrix_sha256` matches HEAD, not the working tree.

---

## 4. Formal25 wall time and the 10×35 estimate

Accepted package (coordinator, not re-accepted here):

- Raw: `8-9-hh3d-3/studio/.local/reviews/gt06-o4-formal-25/`
- Supervisor: `8-9-hh3d-3/studio/.local/reviews/gt06-o4-formal-25-supervisor/`
- Acceptance text: `8-9-hh3d-3/zdoc/reviews/20261003-gt06-owner-critics/coordinator-acceptance.md` lines 26–32 (source `727f9039c1cc83239f5ef1daff13de5e92e37b5ba442e64be8341ca058800b58`, profile `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`, two fresh 35-batch pairs). Plan pointer to Formal25 machinery: plan lines 562–566.

Campaign clock (`campaign-state.jsonl`):

- OPEN `2026-10-03T09:13:56Z`, epoch 1791018836.6794922
- COMPLETE `2026-10-03T10:24:35Z`, epoch 1791023075.9537876
- Wall **4239.274 s = 1 h 10 min 39.3 s** for **2 pairs × 35 batches**
- Supervisor `return.json` `elapsed_seconds` **4240.204** (agrees). That return also says `actual_process_exit_not_yet_observed: true`. Role exits below are separate host captures, not that supervisor flag. Acceptance text says the scheduler terminal was recovered later (`coordinator-acceptance.md` lines 32–33 and 42–47).

Per pair, host-recorded (`host-owner/capture.json` and `editor-host/capture.json`; `process-exit.json` matches):

| Pair | Host PID / exit / elapsed | Editor PID / exit / elapsed | Job |
|---|---|---|---|
| `r00.a01` | 26252 / 0 / **2011.593 s** (33 min 31.6 s) | 29032 / 0 / **2004.656 s** | both `closed`, `zero_observed`, `handle_retained` false, `natural_tree_exit` true |
| `r01.a01` | 49424 / 0 / **2071.000 s** (34 min 31.0 s) | 41892 / 0 / **2064.359 s** | same |

Dataset `dataset.json` (5,114,805 bytes, mtime 2026-10-03 5:24:35 PM local): 2 runs × 35 samples. Every sample in a run has the same host and editor `(pid, process_start)`. Max status gap **1082.058 ms** (pair 0) and **607.993 ms** (pair 1); every batch ≤ 2000. `dropped_commands` 0 and `dropped_telemetry` 0 on both runs. Cleanup: `host_exit_code` 0, `editor_exit_code` 0, `owned_tree_zero` true, `held_handles` 0. Summary `summary.json`: `status` PASS, `failures` [], `gaps` [], `measured_batches` 60, `measured_commands` 60000, `measured_cycles` 6000, `excluded_warmup_batches` 10.

Batch-loop only (monotonic `ended_mono_us - started_mono_us` across 35 samples, excludes process start/stop outside the samples):

- Pair 0 span **1996.034 s** (33.27 min), mean **57.030 s/batch** (batch duration sum 1990.159 s, inter-batch gaps sum 5.875 s).
- Pair 1 span **2055.775 s** (34.26 min), mean **58.736 s/batch** (sum 2050.079 s, gaps 5.696 s).
- Combined batch-loop **4051.809 s / 70 batches = 57.883 s/batch**. This underestimates pair wall. Use the campaign clock for the estimate.

### Estimate for 10 pairs × 35 batches

WIP (and the only way to get 10 pairs without changing the frozen profile) is five Formal25-sized campaigns. Scale the Formal25 campaign wall by 5:

- 5 × 4239.274 s = **21196.4 s = 5 h 53 min 16 s** of P11.
- Cross-check: mean pair from the campaign clock is 4239.274 / 2 = **2119.637 s (35 min 19.6 s)**. × 10 = the same 21196 s.
- Lower bound using only in-process host elapsed, ignoring campaign overhead: 5 × (2011.593 + 2071.000) = **20413 s = 5 h 40 min 13 s**. Overhead inside Formal25 was 4239.274 − 4082.593 = 157 s; five campaigns put that overhead back and return to 21196 s.

P1–P10 from c3e, subtracting the short P11 child: **1611 s = 26 min 51 s**. Add the user’s “about 27 min” as the same measurement (c3e’s 1640 s includes the 29 s short P11).

**P1–P10 + 10×35 ≈ 1611 + 21196 = 22807 s = 6 h 20 min 8 s.**

Night window 19:30 to 07:00 is 11 h 30 min = 41400 s. Margin **18593 s ≈ 5 h 10 min**. A 19:30 start finishes near **01:50**. It fits one night. The plan’s “khoảng 6 giờ” (line 273) matches this soak; the extra ~20 min is P1–P10.

Caveats, all in the direction of “still fits” unless a retry happens:

- Formal25 ran on the afternoon of 2026-10-03, not a quiet night. Night could differ. A 50% slowdown would be ~9.5 h and would still finish before 07:00 (19:30 + 9.5 h = 05:00). A full extra Formal25-sized retry (O1.7 allows 2 infra reruns per day) of one 71-minute campaign still leaves margin.
- Each WIP campaign subprocess is killed at 4 h (`run_gt10pc_matrix.py` WIP line 234). Formal25 was 71 min, so one 2×35 campaign fits that cap. One 10-pair subprocess at this rate (~5 h 53 min) would **not** fit a 4 h wait. The five-campaign split is what keeps each wait under 4 h.
- The outer task timeout is 24 h (`run_gt10pc_task.py` line 149), which also covers 6 h 20 min.
- `CAMPAIGN_WINDOW_SECONDS = 4 * 60 * 60` (`run_benchmark_campaign.py` line 69) is the remaining-window input to the infra-retry gate (`_window_remaining_seconds`, lines 404–409). It is not a hard stop of a passing run. A passing 71-minute campaign does not hit it.

### Split recommendation

No duration split is required for 19:30–07:00. Run all **10 pairs in one night** (five sequential 2-pair campaigns, ~71 min each, plus ~27 min of P1–P10).

If a crash-recovery split is added later, the natural chunk is **2 pairs per window** (one existing campaign, five nights) or **4 pairs per window** (two campaigns, three nights). Two pairs is the unit the frozen profile and the 4 h subprocess cap already match. That feature does not exist yet (next section). Do not split the clock until the runner can append.

---

## 5. Can the runner split P11 across windows on one hash?

**No. Final P11 has to finish inside one matrix process. There is no append-pairs mode with a closure check that accumulates to 10.**

What does exist:

- Inside one GT-06 campaign, a later invocation may resume the unfinished slot of the **same 2 runs** if `campaign.json` is byte-identical, including source and machine (`run_benchmark_campaign.py` lines 6, 1264–1275, 1346–1370). `verify_run_capture` re-hashes artifacts before treating a run as resumable (lines 1148–1188). The loop is `range(profile.PROFILE.process_runs)` and that value is frozen at 2. A third pair cannot be appended to that campaign.
- Resume is not reachable from the matrix runner. HEAD and WIP both `need(not campaign_root.exists(), …)` before launch (HEAD line 250 `GT10PC_P11_FINAL_OUTPUT_EXISTS`; WIP line 290 `GT10PC_P11_CAMPAIGN_EXISTS`).
- The matrix output directory must not already exist (`GT10PC_REHEARSAL_OUTPUT_EXISTS` / mode prefix, WIP `run_rehearsal` around the `need(not output.exists())` check; HEAD has the same guard). A failed night cannot be continued by pointing the runner at the same output.
- Final mode rejects `--rows` (HEAD lines 1023–1024; `run_gt10pc_task.py` lines 72–73). P11 cannot be a second scheduled task that only soaks, and P1–P10 cannot be skipped on a later night, without a code change.
- WIP’s five campaigns are five subprocesses **inside that one matrix process**, each required to be a new directory. That is a timeout split, not a night split. If campaign 3 of 5 dies, campaigns 1–2 are stuck under ids the next attempt will refuse, and the matrix directory cannot be reused.

O1.6 allows several windows on the same hash. The runner does not implement that allowance.

Concrete fix: a window manifest on one frozen closure (payload digest + profile sha256 + toolchain + python exe hash). Each night runs the next 2-pair campaign only if the closure still matches and that campaign id is absent. Completed campaign roots are appended, not rerun. A closure check fails the window if any byte in the frozen set changed. Final verify assembles whatever campaigns the manifest lists until pair count is 10 and the 20 identities are unique. Do not require a fresh matrix directory to re-execute P1–P10 on later nights if those rows are already sealed to the same closure; the plan’s “same hash” rule is the seal, not a single process.

---

## 6. `--verify-only` and source drift

Plan O13.3e (lines 151–152): “--verify-only chạy mọi validator trên raw của một run có sẵn, chỉ để chẩn đoán, không bao giờ ghi PASS.”

### It stops early. It does not score every row. Drift is not a finding beside other rows.

HEAD `_verify_rehearsal_matrix` (lines 377–389) checks schema, then row set, then:

```
need(doc.get('source_closure_sha256') == _payload_digest(_source_files(ROOT)),
     'GT10PC_REHEARSAL_VERIFY_SOURCE')
```

The P11 raw check is the next statement (lines 391–392). On drift, `need` raises before it. `main` catches `ValueError` and prints one `DIAGNOSTIC_FAIL` object with `error` set to that code, and returns 2 (HEAD lines 1047–1050). No per-row result is produced.

HEAD final verify does the same with `GT10PC_FINAL_VERIFY_SOURCE` (lines 410–411) before `_verify_p11_final_row` (line 433).

WIP `verify_matrix` (`gt10pc_matrix_verify.py` lines 90–105) checks schema and row status, then line 102:

```
need(doc.get("source_closure_sha256") == _payload_digest(_source_files(matrix.ROOT)), "GT10PC_VERIFY_SOURCE")
```

`verify_raw_rows` is only called after that (line 105). The docstring of `verify_raw_rows` (lines 108–112) says it is callable on historical raw after source edits and “deliberately issues no matrix PASS.” `--verify-only` does not call it directly. It calls `verify_matrix` (WIP `run_gt10pc_matrix.py` lines 396–403 and 890–903), which aborts on drift first. There is also a second current-tree check inside `_verify_p11_10x35` (line 84, `GT10PC_P11_MATRIX_SOURCE`), reached only if line 102 passed.

So the implementer’s report matches the code: verify of c3e fails closed as soon as the live studio payload digest differs from `matrix.json`’s `a90f378e…`. The working tree edits `run_gt10pc_matrix.py`, which is inside the payload domains hashed by `_source_files` (`release_contract.py` lines 163–186). That is sufficient to change the digest. This audit did not recompute the live digest (that would import the package). The early-exit behavior does not depend on the new digest’s value: any difference raises before row validators.

### PASS

HEAD’s successful verifier **prints** `status: REHEARSAL_PASS` (lines 397–398) or `status: FINAL_PASS` (lines 486–487). It does not rewrite `matrix.json`. It still records the word PASS in the verifier result. That conflicts with plan line 151.

WIP’s success result is `status: RAW_VERIFIED`, `authority: 0`, `acceptance: False` (`gt10pc_matrix_verify.py` lines 217–218). Process exit is still 0 (`run_gt10pc_matrix.py` WIP lines 898–903). It does not write a PASS file. That matches “diagnostic only, never write PASS” better than HEAD. It still does not continue after source drift.

Fix: on closure mismatch, keep going through `verify_raw_rows`, add a finding `SOURCE_DRIFT` with expected vs observed digest, set status `DIAGNOSTIC_SOURCE_DRIFT`, `acceptance: false`, and return exit 2. Never emit `REHEARSAL_PASS` or `FINAL_PASS` from `--verify-only`. Do not update `matrix.json`.

---

## GAPS

### BLOCKER — HEAD final P11 is 2×35, not 10×35

HEAD `_p11_full_final` (git-show lines 238–314) runs one `run_campaign` and labels it `formal-2x35` with measured 60 / 60000 / 6000. Plan lines 273–276, 393–394, and 1458–1459 require 10 fresh pairs × 35 batches on the release hash.

Fix: land the WIP shape after it is finished: five clean `run_benchmark_campaign.py` campaigns, each frozen v6 2×35, 20 unique (role, pid, start) identities, aggregate measured 300 / 300000 / 30000, `coverage` `formal-10x35`, each campaign bound to the release archive bytes. Do not change `BenchmarkProfile.process_runs` (the version lock would reject it). Delete or redirect the stale `_verify_p11_final_row` 2×35 check so it cannot be wired back. Freeze and commit before any final task. c3e does not need to be remade as a soak; it is a valid short rehearsal of the HEAD runner.

### MAJOR — no same-hash window resume for the 10 pairs

Plan lines 394, 523, and 1458–1459 allow several windows on one hash. The matrix runner refuses an existing output directory and an existing campaign root, and final mode refuses `--rows`. A 6 h 20 min task that dies at pair 7 cannot continue.

Fix: as in section 5. Not required to fit 19:30–07:00, and required before anyone relies on a multi-night split. Until then, schedule one night and treat a mid-soak failure as a new id after the closure is still the same (infra) or after a new freeze (product/verifier).

### MAJOR — `--verify-only` aborts on source drift before row validators

HEAD lines 388–389 and 410–411. WIP `gt10pc_matrix_verify.py` line 102. Plan lines 151–152 say run every validator on the existing raw and only diagnose.

Fix: as in section 6. The c3e rejection the implementer saw is this early `GT10PC_VERIFY_SOURCE` / `GT10PC_REHEARSAL_VERIFY_SOURCE`, not a P11 content failure.

### MAJOR — HEAD verifier result status is PASS

HEAD lines 397–398 and 486–487 print `REHEARSAL_PASS` / `FINAL_PASS`. Plan line 151 forbids recording PASS from `--verify-only`.

Fix: keep WIP’s `RAW_VERIFIED` with `acceptance: false` and authority 0. Do not write that status back into `matrix.json`.

### MAJOR — WIP still contains a 2×35 final-row verifier

Working-tree `run_gt10pc_matrix.py` lines 336–339 require `formal-2x35` while lines 328–332 emit `formal-10x35`. Currently uncalled. The live checker is `gt10pc_matrix_verify.py`.

Fix: remove `_verify_p11_final_row` or make it call `_verify_p11_10x35`. Add a test that a 2×35 row is rejected in FINAL and a five-campaign 10×35 row is what verify reads.

### MINOR — p11a import stage saw one active process at wrapper exit

`gt06-p11-short-d0782023/import-host/capture.json` has `active_at_wrapper_exit: 1`, then `active_before_cleanup: 0`, `natural_tree_exit: true`, job closed and zero. c3e’s import stage and both editor stages are 0. The rehearsal checker looks at aggregated `capture.json` jobs, which are closed/zero. Not a soak sample.

Fix: none for the 10×35 gate. If the short-cycle verifier is tightened, decide whether `active_at_wrapper_exit` must be 0 or whether cleanup-zero is enough, and apply it to both stages.

### Not a gap

- c3e and p11a being one cycle. Plan lines 273–274 and C2 (lines 203–204) ask for that rehearsal.
- Task closure `1301d0b2…` vs matrix closure `a90f378e…` on c3e. Different hash functions (`run_gt10pc_task.py` lines 48–54 vs payload digest).
- Formal25 supervisor `actual_process_exit_not_yet_observed`. Role exits are in `process-exit.json`. Do not treat the supervisor flag as the host/editor exit.

---

## Files read

- `8-9-hh3d-3/zdoc/8-9-godot-blender-agent-studio-plan.txt` (P11 273–276, O13.3e 151–152, O1 375–411, O4.1 466–483, split 523 and 1458–1459, Formal25 pointer 562–566)
- HEAD and working tree `8-9-hh3d-3/studio/tests/conformance/run_gt10pc_matrix.py`
- Working tree `8-9-hh3d-3/studio/tests/conformance/gt10pc_matrix_verify.py`
- `8-9-hh3d-3/studio/tests/replay/benchmark_profile.py`, `run_benchmark_campaign.py`, `run_native_benchmark.py`, `run_gt10pc_task.py`
- `8-9-hh3d-3/studio/package/release_contract.py` (`_source_files`, `_payload_digest`)
- Evidence trees named in sections 2 and 4
- `8-9-hh3d-3/zdoc/reviews/20261003-gt06-owner-critics/coordinator-acceptance.md`
