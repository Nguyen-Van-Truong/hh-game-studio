# GT-10-PC pre-review: P7 and P10

Package: `8-9-hh3d-3/studio/.local/reviews/gt10pc-rehearsal-20261012-c3e`
Judged against committed HEAD (`git show HEAD:8-9-hh3d-3/studio/tests/conformance/...`).
Working-tree WIP was read only to see whether a gap is already being fixed.
c3e `matrix.json`: `status=REHEARSAL_PASS`, `authority=0`. Task receipt `gt10pc-rehearsal-20261012-c3e-task/task-terminal.json`: `last_task_result=0` (scheduler only).

Paths below are relative to the c3e directory unless noted.

Native vs simulated (P7): **5 real OS kills, 3 real Stops, 0 simulated exits.**
HEAD `run_gt10pc_p7.py:launch_worker` calls `process.kill()` and requires a non-zero `process.wait()` for kill, or `ConsumerInstall.stop_existing` plus unpark and exit 0 for Stop. Cut points are in-process `unittest.mock` hooks in `gt10pc_lifecycle_crash_worker.py:instrument` (the worker parks; the parent then kills or stops that live PID). No case writes a fake exit.

---

## P7

### 1. Requirement

TX14 crash, at most 8 native cases: kill and Stop between install, upgrade, and rollback phases; network loss and token rotation only in phases that use them, otherwise `NOT_APPLICABLE` with a reason; last-good intact; lookup by the same `command_id`; no duplicate effect. A second retry must leave install/project/state unchanged, and the restored addon must match the selected release hashes.

### 2. Evidence in c3e

Eight cases in three producers. Group host receipts (the producer process, not the killed worker):

| Group | Host receipt | Producer PID | Exit |
|---|---|---|---|
| first (3) | `children/p7-native-a-host.json` | 13772 | 0 |
| second (3) | `children/p7-native-b-host.json` | 12536 | 0 |
| third (2) | `children/p7-native-c-host.json` | 12060 | 0 |

Stdout of each group is `{"status":"P7_DIAGNOSTIC_PASS","cases":N,"acceptance":false}`. Reports: `p7-native-a/p7.json`, `p7-native-b/p7.json`, `p7-native-c/p7.json` (schema `hh-gt10pc-p7-native-recovery-1`, `acceptance=false`, `native_required=true`). Old manifest `54d887ec8d87b30a6385280539ae06a8d240c98fb020568564b127f075538306`, new `5583cf7d9ab4eb03b9a2be54d80968743001d15b89d75cb0f6b09a482b4bf4b1`.

Per-case raw files: `p7-native-{a,b,c}/cases/<name>/cut.json` (victim writes its own PID), `worker-host.json` (parent writes `pid`, `actual_exit`, `disposition`, `tree_verified`), `request.json`, empty `worker-stderr.txt`. Stop cases also have `external-stop.json` and `cut.unpark`. There is no `retry-proof.json`, `project-before.json`, or `project-final.json`. `worker-host.json` has no killer PID and no process-tree list. `tree_verified` is a boolean (`job active count == 0` in `launch_worker`), not a tree.

| Case | Phase | Fault | Victim PID | Exit | Who killed | Last-good state hash before → after recovery | Active before → after | Lookup |
|---|---|---|---|---|---|---|---|---|
| `install-release-renamed` | install / `release-renamed` | kill | 27032 | 1 | not recorded | `a1a97af8…c384` = same, rev 2→2 | old = old | `p7.install-release-renamed` COMMITTED rev 3 after the one retry |
| `install-stop-staged` | install / `staged` | stop | 40768 | 0 | `external-stop.json` `stop.install.staged` CANCEL_PENDING, durable | `41fa2675…feea` → `e1b4455b…60ea`, rev 2→3 | old = old | same id CANCELLED `STOP_BEFORE_INTENT`, rev 3 |
| `upgrade-selector-before-addon-intent` | upgrade / `selector-before-addon-intent` | kill | 20088 | 1 | not recorded | `71b486e6…b3c2` → `0978acbf…1d71`, rev 2→3 | old → new | same id COMMITTED rev 3 |
| `upgrade-stop-addon-intent` | upgrade / `addon-intent` | stop | 45600 | 0 | `external-stop.json` `stop.install.addon-intent` DRAINING | `92e4ae92…5f82` → `f0fd8ed8…84db`, rev 2→3 | old → new | same id COMMITTED rev 3 |
| `upgrade-old-addon-moved` | upgrade / `old-addon-moved` | kill | 30376 | 1 | not recorded | `e28252cd…22be` → `db63cc30…f7c7`, rev 2→3 | old → new | same id COMMITTED rev 3 |
| `rollback-new-addon-moved` | rollback / `new-addon-moved` | kill | 33548 | 1 | not recorded | `de34474f…d2a0` → `a1306532…acb3`, rev 4→5 | new → old | same id COMMITTED rev 5 |
| `rollback-stop-before-selector` | rollback / `before-selector` | stop | 4308 | 0 | `external-stop.json` `stop.rollback.before-selector` CANCEL_PENDING | `57cbf858…9fcd` → `6e15e9c0…be8a`, rev 4→5 | new = new | same id CANCELLED `STOP_BEFORE_INTENT`, rev 5 |
| `rollback-journal-published` | rollback / `journal-published` | kill | 2860 | 1 | not recorded | `df5af9ba…426e` → `3114b28d…cdcc`, rev 4→5 | new → old | same id COMMITTED rev 5 |

Full hashes are the values above; the short form is only for the table. Disk readback `cases/<name>/install/.install.json` has exactly one row for each `p7.<name>` (no duplicate command key). Final revision on disk matches `p7.json` `final.revision`. Both release directories remain, and `manifest.json` sha256 equals the directory name (sampled on all three groups). That shows the release identity is still present after the run. It does not show a pre-crash file ledger.

`after_recovery` in `p7.json` is taken after `ConsumerInstall` reopen (`run_case`), which completes a durable WAL before the snapshot. Only `install-release-renamed` keeps the same state hash across that boundary. Stop-before-intent keeps the same active release but changes the state hash because the CANCELLED row is stored. Late cuts already show the new active release in `after_recovery`. There is no on-disk snapshot from the moment after the kill and before reopen.

Lookup and the single retry are equal inside `p7.json` (`lookup` == `retry`). Final revision equals the post-recovery revision, so the one retry did not add a second revision when a lookup already existed. The early kill `install-release-renamed` goes rev 2 → 3 once (the interrupted install is completed once). There is no second retry artifact.

Restored addon bytes: for all 8 cases, the five files under `project/addons/hh_studio` from the active release payload (`godot-addon/addons/hh_studio/*` plus `protocol/jcs_godot.gd`) hash-match the active release. HEAD does not record or check that comparison. Post-recovery Godot probes exist (`native/godot-host.json`, `native/parse-host.json`, `native-driver/driver-host.json`, all exit 0) for fixture `gt09-arena` only. Those are play probes, not the kill receipt.

Network loss and token rotation: no case file and no `p7.json` field contains `NOT_APPLICABLE`, network, or token rotation. These lifecycle phases do not open a network client or a session token (local WAL; package lock is offline-only). The required NA reason is absent.

### 3. What HEAD checks

- `run_gt10pc_p7.py:launch_worker` — kill or stop the child; write `worker-host.json` with victim pid and `actual_exit`.
- `run_gt10pc_p7.py:run_case` — one retry; `lookup == retry`; revision increases only when `lookup_before_retry` is None (`P7_RETRY_EFFECT_DUPLICATED`); project core and manual note unchanged. No second retry. No addon-byte compare. No NA record. No pre-reopen hash file.
- `run_gt10pc_matrix.py:run_rehearsal` — child exit 0 / `tree_verified` / not timed out, then `p7.json` schema, `acceptance is False`, `native_required`, and `len(cases)` in {3,3,2}. Does not open `worker-host.json` or `.install.json`.
- `run_gt10pc_matrix.py:_verify_rehearsal_matrix` — for P7, only `rows["P7"]["status"] == "REHEARSAL_PASS"`.
- `run_gt10pc_matrix.py:_verify_final_matrix` — `cases == 8`, three producers, and each embedded `child.exit_code/tree_verified/timed_out` copied into `matrix.json`. Does not re-read case files.

### 4. Gaps

**BLOCKER. Per-case process-tree receipt does not say who killed which PID, and HEAD verify does not read the raw kill receipt.**
`worker-host.json` is written by the killer and stores the victim pid, exit, and a boolean `tree_verified`. It does not store the killer pid or a process tree. `children/p7-native-*-host.json` is the producer (exit 0), not the killed worker. Rehearsal verify accepts the matrix status flag; final verify accepts child flags already copied into `matrix.json`.
Fix: for each case, have an independent host helper record killer pid, victim pid, exit code, and job-tree emptiness; point the matrix child at that file. Make verify re-read `cut.json`, `worker-host.json`, and the single `.install.json` command row, and fail if those disagree.

**MAJOR. Network loss and token rotation are not recorded as NOT_APPLICABLE.**
No phase of this installer uses a network client or a session token, so each of the 8 cases must say NA with that reason. c3e has zero such records.
Fix: write one NA row per case for network loss and one for token rotation, reason “local lifecycle WAL; no network client and no session token in this phase.” Verifier requires all 16 reasons (or 8 combined records) and rejects a bare omission.
WIP: `run_gt10pc_p7.py` and `gt10pc_p7_verify.py` do not add this.

**MAJOR. Second retry is not in c3e, and HEAD never checks addon bytes against the selected release.**
HEAD `run_case` performs one retry only. c3e has no `retry-proof.json`. On disk the final addon bytes do match the active release (5 files, 0 mismatches, all 8 cases), but nothing in HEAD compares them, and the match is not saved as a ledger.
Fix: after recovery, call the same `command_id` a second time and persist install, project, and state hashes before and after; hash `addons/hh_studio` against the selected manifest (`plugin.gd`, the rest of the addon, `jcs_godot.gd`) plus the manual note. Verifier re-reads those files.
WIP: `run_gt10pc_p7.py:run_case` writes `retry-proof.json`, `project-before.json`, `project-final.json` and checks `P7_SECOND_RETRY_EFFECT` and `P7_SELECTED_ADDON_BYTES`. `gt10pc_p7_verify.py:verify_p7` re-reads them, but it requires schema `hh-gt10pc-p7-native-recovery-2`. c3e is schema `-1` and lacks those files, so WIP does not make c3e pass.

**MAJOR. Last-good before/after is not an independent file snapshot.**
State hashes above live only inside producer-written `p7.json`. `after_recovery` is after reopen, so late cuts already show the committed release. Release manifests still match their directory names, which shows the identity was not replaced by a different file, not that every payload byte was unchanged at the kill.
Fix: immediately after kill/stop and before `ConsumerInstall` reopen, write a hash ledger of `.install.json` and both release trees. Verifier recomputes `state_digest` and those file hashes.
WIP: `verify_p7` recomputes `state_digest` on the embedded snapshots and checks second-retry install/project equality. It does not add a pre-reopen ledger. Not applicable to c3e’s schema `-1` files.

### 5. WIP vs this package

WIP addresses the second retry, addon-byte compare, and a raw re-read of worker-host pid/exit (`gt10pc_p7_verify.py:verify_p7`, called from `gt10pc_matrix_verify.py:verify_raw_rows`). It does not name the killer, does not write NOT_APPLICABLE, and does not snapshot last-good before reopen. It cannot verify c3e until a new run emits schema `-2` and `retry-proof.json`.

---

## P10

### 1. Requirement

GT-08A PC rows (Windows import/export and Linux headless import/export) plus K8 and K10, on the copy installed from the package, for both fixtures.

GT-08A scenario table (`studio/build/ci/gt08a_matrix.py` `SCENARIOS`): W01 clean checkout, W02 Windows import, W03 Windows export, L01 Linux-headless import, L02 Linux-headless export, plus offline cache/negative/signature rows. K8 is catalog publications with command_id and readback on two fixtures. K10 is 60 Hz pressed/held/released trace plus seed, pause/resume/quit, replay, save/reload, perf budget, and clean logs, per fixture.

### 2. Evidence in c3e

Installed from `artifacts/windows/release.hhpkg`. Both phases share manifest `85546002a7086f5a7e0e44edead5e0ecc7babcc70253e4d6481a8ccc54068e5b`.

Producer host receipts:

- `children/p10-installed-gt08a-host.json` target_pid 41632 exit 0 (wrapper 27260 in the receipt).
- `children/p10-installed-catalog-host.json` target_pid 33212 exit 0 (wrapper 44040).

**GT-08A** (`p10-gt08a/gt08a.json`, dirs `p10-gt08a/gt08a/W02` and `W03` only):

- W01 is a static PASS (unicode path, zdoc excluded). No process.
- W02 Windows import: Godot `--headless --editor --quit` on `gt08a/work/fixture Ñé with spaces` (copy of installed `fixtures/sample-game`). Embedded process `exit_code=0`, `timed_out=false`, `tree_verified=true`. No `target_pid`. No `host.json`. `W02/stderr.txt` is empty (0 bytes); `W02/stdout.txt` is 1385 bytes.
- W03 Windows export: `--export-release "Windows Desktop"` → `W03/fixture.exe` (109127680 bytes) and `fixture.pck`. Same process shape: exit 0, no PID. `W03/stderr.txt` empty.
- L01 and L02 directories do not exist. No Linux headless import or export.
- Fixture is `sample-game`, not arena and not room.

`tree_verified` in this process dict is `proc.poll() is not None` (`gt08a_matrix.py:run_process`), not a job tree, and the dict is embedded in `gt08a.json` by the producer.

**Blender content, native, from the installed runtime.**
`p10-catalog/children/blender-content-host.json`: target_pid 42812, exit 0, stderr empty.
Command is `p10-catalog/installed-runtime/studio/tests/conformance/run_gt09_blender_content.py`.
Result `p10-catalog/installed-runtime/reviews/gt09-content-p10-p10-catalog/result.json`: `native.process_exit` pid 39428 exit 0, `publication_readback.glb` sha256 `39f38dd95130f5c7f28e48e05071264295dc7f0f46ac1c440111fd4e45e0bb8b` (walk clip, bones root/spine/leg.l/leg.r). The Blender pid is inside that result JSON; the independent host pid is the Python wrapper.

**K8, both fixtures (arena and room).**
Registered probes, host exit 0, stderr empty:

- `children/registered-arena-host.json` pid 31092
- `children/registered-room-host.json` pid 27908

`installed-runtime/studio/.local/reviews/o2-registered-authoring-p10-catalog-arena/registered-owner-result.json`: fixture `arena`, 18 `command_ids`, `receipt.readback_ack=true`, `native_process` pid 43348 exit 0.
Room file: fixture `room`, 14 `command_ids`, `readback_ack=true`, pid 19660 exit 0.
Publications:

- `children/publication-arena-host.json` pid 10064 exit 0
- `children/publication-room-host.json` pid 2556 exit 0

`o2-publication-gt10pc-p10-p10-catalog-arena/result.json`: `command_id` present, `readback_sha256` / `readback_ack`, scene `scenes/arena.tscn`, catalog command ids `recipe.node.*` (18).
Room result: scene `scenes/room.tscn`, `room.node.*` / `room.bind.*` (14). Both `status=DIAGNOSTIC_PASS`, `native_fixture_observed=true`.

**K10, both fixture names, incomplete raw trace.**
`p10-catalog/k10-conformance.json`: `status=CANDIDATE_PASS`, fixtures `arena_2d` and `room_3d`, `errors=[]`. Host `children/k10-conformance-host.json` pid 2888 exit 0, stderr empty.
`native-observation.json` under each publication (flags written by the probe, not a trace file):

- Arena: `replay_hash_equal=true`, `checkpoint_reload_observed=true`, `perf_budget_ok=true`, `perf_samples=150`, `ticks=150`, `saved_world_path=res://scenes/arena.tscn`. No `pressed`, `held`, `seed`, `pause`, `menu`, or `quit`. The word `trace` does not occur. `input_released=true` only.
- Room: `input_trace_ok=true` (boolean only), `replay_hash_equal=true`, `checkpoint_reload_observed=true`, `perf_budget_ok=true`, `perf_samples=60`, `ticks=60`. No pressed/held/released samples, no seed, no pause/resume/quit.
Publication stdout files: 11 per fixture, none contain `ERROR`, `WARNING`, or `SCRIPT ERROR`. Child stderr files are 0 bytes.

### 3. What HEAD checks

- `gt10pc_p10.py:run_gt08a` — runs W01–W03 only, from the installed `build/ci/gt08a_matrix.py`. Does not call `matrix_run`, so L01/L02 never start.
- `gt10pc_p10.py:_run_catalog_processes` — Blender, then registered + publication for `arena` and `room`, then `gt09_fixture_conformance.py`. Requires each child clean and result `DIAGNOSTIC_PASS` / conformance `CANDIDATE_PASS`.
- `gt10pc_p10.py:verify` — re-hashes the installed runtime closure (`runtime-snapshot.json` vs files on disk) and catalog child stdout/stderr (`_verify_child_receipt`). GT-08A proof is `gt08a.json` row ids `["W01","W02","W03"]` all `status==PASS`, plus the embedded process dict’s exit/tree flags. It does not open `W02/stdout.txt`, does not require a PID, and does not look for L01/L02. K8/K10 proof is publication `DIAGNOSTIC_PASS`, registered `native_process.exit_code==0`, and `k10-conformance.json` `CANDIDATE_PASS`. It does not open `native-observation.json` for trace, replay, save, or perf.
- `run_gt10pc_matrix.py:run_rehearsal` — calls `verify()` once at produce time, then stores `REHEARSAL_PASS`.
- `run_gt10pc_matrix.py:_verify_rehearsal_matrix` — P10 passes if `status==REHEARSAL_PASS`.
- `run_gt10pc_matrix.py:_verify_final_matrix` — two producers, one manifest hash, embedded child exit flags. Does not re-call `verify()`.

### 4. Gaps

**BLOCKER. Linux headless import/export did not run, and the Windows rows have no host PID.**
c3e shows W02 and W03 only, on `sample-game`, with exit 0 inside `gt08a.json` and no pid. L01/L02 are absent. `verify` accepts that embedded dict. Rehearsal verify-only then accepts `REHEARSAL_PASS` without opening `p10-gt08a`.
Fix: from the installed runtime, run L01 (pinned Linux headless import) and L02 (Linux export) through the shared host helper so each row has `*-host.json` (target pid, exit) plus stdout/stderr hashes. Point `verify` at those files and require W02, W03, L01, L02. Do not treat `proc.poll() is not None` as a process tree.
WIP: `gt10pc_p10.py` is not modified. `gt10pc_matrix_verify.py:verify_raw_rows` calls the same `verify()`, so a future verify-only would still accept W01–W03 without L01/L02 or a PID.

**MAJOR. K10 raw trace/pause/seed is missing on both fixtures; the verifier trusts CANDIDATE_PASS.**
Both arena and room have host receipts, clean stderr, replay and checkpoint-reload and perf booleans. Neither has a 60 Hz pressed/held/released trace, a seed, or pause/resume/quit. Arena does not even have `input_trace_ok`.
Fix: persist the trace (pressed/held/released, seed, pause freezes tick, save/reload readback) per fixture and require those fields from `native-observation.json` (and the engine host pid) inside `gt10pc_p10.py:verify`. `CANDIDATE_PASS` alone must not pass the row.
WIP: does not add this. K8 itself (catalog command ids and `readback_ack` on arena and room, scripts under `installed-runtime`) is present in the raw files; the verifier still does not re-read `readback_ack` or the command id list.

**BLOCKER (both rows). HEAD verify-only trusts producer-written PASS fields.**
`_verify_rehearsal_matrix` checks `status==REHEARSAL_PASS` for every row except P11. `_verify_final_matrix` checks counts and child flags stored in `matrix.json` by `run_rehearsal`. P7 case files and P10 `gt08a.json` / observations are not re-opened. Produce-time `need()` and `gt10pc_p10.verify` are not a later verifier: they are the same writer that emits the PASS flag.
Fix: `--verify-only` must call a reader that recomputes from `worker-host.json`, `.install.json`, `W02`/`W03`/`L01`/`L02` host files, catalog child host files, and `native-observation.json`.
WIP: `gt10pc_matrix_verify.py:verify_raw_rows` is that reader for a future run. On this package, `verify_p7` fails closed on schema `-1` (no `retry-proof.json`). `verify_p10` still trusts the GT-08A process dict and `CANDIDATE_PASS`.

### 5. What is supported

- P7: 5/8 real `process.kill` (exit 1) and 3/8 real Stop (exit 0). Same `command_id` is stored once. One retry did not bump revision a second time. Final addon bytes match the active release on disk, unchecked by HEAD.
- P10: Blender content was produced by the installed `run_gt09_blender_content.py` with a host exit 0 and a GLB readback. K8 catalog publications with command ids and `readback_ack` ran on arena and room. K10 probes ran on both fixtures with clean stderr and replay/perf/reload flags, without the 60 Hz trace body. GT-08A Windows import/export ran from the installed copy on `sample-game` only. Linux headless import/export did not run.
