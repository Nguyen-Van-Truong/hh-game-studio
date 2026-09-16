# S49 final executor source review

AUTHORITY=0. Independent bounded read-only review, 2026-09-17. Scope: `cli_job.py`, executor lifecycle/admission/deadline, and the new `profile-validate` path. No source edits, test execution, Docker/engine launch or GT-03 acceptance signature. Coordinator runtime evidence was still being produced; this report does not certify it.

## Result

One actionable cancellation-recovery limitation remains. No additional ordinary-Exception-path false-clean/removal proof or profile-specific deadline/admission bypass was found in this bounded source review. This is not a complete sandbox audit. Root acknowledged the cancellation limitation and assigned its fix/regressions to S50 after the S49 checkpoint; frozen S49 source remains unchanged.

## P2: constructor cancellation can bypass retained cleanup admission

`studio/godot-addon/cli_job.py:195-228` registers a new owner in `_LIVE`, creates a native handle and configures/assigns it, but only catches `Exception`. A `KeyboardInterrupt` or `SystemExit` from configuration or assignment therefore bypasses `_failure`, checked constructor cleanup and `cleanup_owner` attachment. The retained owner remains in `_LIVE` with a live native handle but is absent from `HOLDS`.

`require_no_holds()` (99-102) and `retry_cleanup()` (231-242) inspect only `HOLDS`. Consequently the next caller is not rejected for that failed owner, and the public retry path has no work to retry. Repeated cancellation can retain handles until process exit or the 16-owner capacity limit. The reference is not lost from Python's private `_LIVE` registry, but it is lost from the documented cleanup/admission path.

At the integration point, `linux_executor.py:444` cannot receive a Job owner when `create(process)` never returns; its handler (466-469) also catches only `Exception`. Its finally block still attempts to kill/reap the gated helper and close pipes, but has no local Job owner to query/close. This is a host cancellation/recovery defect, not evidence that an untrusted project can trigger a constructor interruption or pass the GO gate. It does not manufacture clean success. Complete OS process death releases process handles; that separate host-death scenario does not test resumable in-process cancellation.

Required S50 focused regressions, without changing this frozen snapshot:

1. Inject both `KeyboardInterrupt` and `SystemExit` at native configure and assign after successful creation. Assert either checked zero/close or a retained reachable cleanup owner; unresolved ownership must block new creation and remain visible to bounded retry.
2. Combine each cancellation with native query/terminate/close failure. Check no discarded handle, no double close after successful retry, and no clean ownership snapshot while tainted.
3. Inject cancellation during `active_count`, `terminate` and `close`; confirm consistent hold/propagation semantics, especially after a handle exists but before successful checked close has been recorded.
4. At `_cli` integration, cancel Job creation and later operations while a fake helper is gated/running. Require helper/pipe cleanup or explicit retained ownership, evidence that stays dirty, and no missing-container/removal proof from an incomplete Job row. Use pure mocks first; any native follow-up must be separately owned and bounded.

## Verified source behavior and limits

* `cli_job.py:93-184` retains ordinary native query/terminate/close failures, bounds registered owners, requires an actual zero-active query before checked CloseHandle, and avoids double close. Constructor ordinary failures preserve cleanup ownership when cleanup fails (214-227).
* `linux_executor.py:438-528` checks existing Job holds before Popen, gates Docker behind successful Job assignment, records reader exceptions/EOF, continues Job cleanup after helper kill/wait errors, skips joining never-started readers, retries reaping after verified Job zero, and retains unfinished pipes/readers. These resolve the earlier ordinary cleanup findings.
* `_cli_done` (530-546) requires actual expected exit, no timeout/cap/read/evidence error, both EOFs, zero Job count, configured/assigned/closed/zero owner facts, and no taint/retained handle/native failure. `_missing` and owned removal use this same strict predicate (306-309,771-778).
* Admission uses the same global named mutex across source copies, waits at most one second, and holds it through owned cleanup or persisted ambiguity (216-255,691-798). An abandoned mutex still goes through exact record reconciliation and labelled inventory. Release/close errors retain a local owner; a failed release attempts a durable rejecting phase. Mutex abandonment indicates potentially inconsistent protected state, so reconciliation is necessary. [Microsoft mutex objects](https://learn.microsoft.com/en-us/windows/win32/sync/mutex-objects)
* `_reconcile_owner` (311-349) binds exact name/label/image/full ID, observes stopped/PID-zero state before removal, requires checked missing proof, and denies unknown labelled containers. A missing name after an unresolved create stays ambiguous. It never grants cleanup authority from a label alone. The global mutex/per-account record intentionally causes denial for another account's unknown orphan.
* `profile-validate` qualifies exactly eleven input files before container work; its fixed driver runs parse, import and readback sequentially beneath the **same** PID1 deadline (158-214). A third read-only harness bind is exact-inspect checked (574-576,611-619); the harness is separately pinned and compared before start and after shutdown (186-189,737-741,808-815). No caller argv or per-phase deadline reset was added.
* The bootstrap verifies PID1, UID, timeout hash and restrictive Yama before exec; commands retain TERM plus one-second kill-after and no foreground/init mode. Linux PID1 signal restrictions and namespace teardown support this design; Yama restricts child-to-ancestor tracing. Coreutils 9.1 clears `kill_after` after scheduling final KILL so later handled signals do not reset it. Scheduling/backend delays remain outside a hard real-time guarantee. [PID namespaces](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html), [Yama](https://docs.kernel.org/admin-guide/LSM/Yama.html), [pinned coreutils source](https://github.com/coreutils/coreutils/blob/v9.1/src/timeout.c)

## Evidence boundary

The reviewed tests include ordinary constructor/close failure, EOF failure, helper kill/wait error, never-started readers, dirty missing/removal proof, lost create reply, admission recovery, and fixed profile commands/mounts. They do not cover BaseException cancellation. Tests were read, not rerun during this review.

Earlier `20260917-gt03-s49-executor-probes/host-death-05` is evidence for its older `a38367a...` source, not this executor's `20e6a13b...` closure. Fresh same-closure actual profile, concurrent admission, hostile PID1 and host-death results remain the coordinator's responsibility. Source review alone cannot transfer that proof.

The documented remaining limits are material: same-user host/source custody is unprotected; snapshots precede admission; aggregate retained evidence storage and other Docker users are not capped; complete IPC/PTY/inode/OOM exhaustion coverage is absent; unknown/ambiguous ownership has no automatic waiver. These are diagnostic boundaries, not newly discovered profile bypasses. `public_ack`, `sandbox_acceptance` and API `host_death_acceptance` remain false.

## Reviewed SHA-256

Paths are relative to `8-9-hh3d-3/studio`. Main source hashes were checked again after inspection and remained unchanged.

| File | SHA-256 |
| --- | --- |
| godot-addon/cli_job.py | da93593e8bf0cac6d26904322f81ebfe77f46de8c882c23f887e2b4fe28cdacb |
| godot-addon/linux_executor.py | 20e6a13b0e78a519d50ee253cf9f9aa9b04ee5429a00a689350f64f54ed05645 |
| godot-addon/validator-toolchain.lock.json | f9a5400b04be557b40514321bbfea31c9bee627845636db85ffacb363fe4f71d |
| godot-addon/validation_bootstrap.gd | 1e67888029b75945eb11d2730936e98a5028884d7746a4a2be9a7304cf5298cf |
| godot-addon/LINUX_EXECUTOR.md | 42379743a8423289715d114cbe6e1ea3babbe322d0f8bcfa192bcaa86f9575b1 |
| tests/godot/test_cli_job.py | 203dd76bfbd2e8fe8ca00c1160fec61d7102515a47f424e529c1cefe7601f1dc |
| tests/godot/test_linux_executor.py | 1015e55eb86179367107b2f780808dca5113bc47385537513db04fdb20b0bdba |
| tests/godot/test_linux_cli_cleanup.py | c5fa9e00777cbb424ec9127a519eaddb6c535c1e628239ac376e7cc592560d5d |
| tests/godot/test_linux_profile.py | 9638b9c3378b47c89fa333976cdf6b0d2e3043aa2be491605b9c201fdcd8e56f |
