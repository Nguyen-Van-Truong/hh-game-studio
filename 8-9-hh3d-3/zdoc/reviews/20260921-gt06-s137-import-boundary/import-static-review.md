# S137 static import-boundary review (AUTHORITY=0)

**Scope.** Read-only review of the pinned Linux profile executor, bootstrap runner, and the raw S134/S135 profile packets. No Godot, Docker, test, replay, or source/plan mutation was run. This note is diagnostic attribution only; it is not a GT06 verdict.

## What the profile command actually does

`studio/godot-addon/linux_executor.py:192-205` builds one sequential Python driver. It launches, in order, `parse`, `import`, then `readback`; each child is run with `subprocess.run`, a phase-end marker is printed with the child return code, and any nonzero code causes the wrapper to exit **45**. The import command is fixed at lines 373-376 (`--headless --editor --import --path /project ... fixture.tscn`). `readback` cannot start until an `HH_PROFILE_PHASE_END import 0` has been printed.

The driver is wrapped at `linux_executor.py:208-213` by the pinned `/usr/bin/timeout`: `--signal=TERM --kill-after=1s 19s` when `timeout_seconds=20`. The implementation admits 1..20 seconds (`:209`); the documented budget is TERM at `max(1, timeout-1)`, KILL one second later, total 2..20 seconds (`godot-addon/LINUX_EXECUTOR.md:106-107`). The host Docker attach uses `timeout_seconds + 2` (`linux_executor.py:803`), therefore **22 seconds** for these packets. The 22-second host budget is not the 19/20-second in-container phase supervisor.

Container limits are fixed in source: `ULIMITS` has `cpu=10` seconds (soft=hard), plus fsize 8 MiB, core 0, nofile 256 and msgqueue 8192 (`linux_executor.py:37`; applied as identical soft/hard values at `:620-621`). Creation also fixes memory=1 GiB, memory+swap=1 GiB, one CPU, 64 PIDs and stop-timeout=2 (`:614-619`). The packet `created-inspect` rows for S134-02/S134-03/S135-03/S135-04 all report these exact values.

## Who can send SIGKILL, and what the packets exclude

There are three different kill paths; they must not be conflated:

* The POSIX `SIGKILL` calls in the pinned `build/bootstrap/run_fixture.py:241-248` and `:262-272` kill that runner's own process group on a timeout/tree-cleanup. This is not the Linux container path here: `linux_executor._cli` launches its own Windows helper (`linux_executor.py:468`, `_HELPER` at `:38`) and the packet reports Windows Job ownership. The helper cleanup `process.kill()` at `:515-518` kills only the host Docker-CLI helper. `cli_job.py` explicitly describes itself as “no Docker/container authority” (line 1); its `TerminateJobObject` is for that helper Job (`:82-84`).
* The container-level Docker `kill` calls are conditional watchdog/cleanup calls (`linux_executor.py:810-812`, `:829-831`) after a fresh inspect says `State.Running`. They are not unconditional and would be reflected by a host watchdog/cleanup action. The S135 `after-command-inspect` row already says `Running=false`, `Pid=0`, `ExitCode=45`; S135 `engine-host.json` has `timed_out=false`, `stream_cap_exceeded=false`, both reader EOFs, and a closed/zero Windows Job. Therefore the host did not need the running-container watchdog path for these failures.
* The in-container supervisor is the only pinned component configured to signal the profile command at a wall deadline: `/usr/bin/timeout` TERM at 19 seconds and KILL at 20 (`linux_executor.py:47-53`, `:212-213`). However, if this supervisor killed the Python driver/process group at its wall deadline, the Python driver could not execute its `print("HH_PROFILE_PHASE_END import -9")` line (`:202-205`). The observed marker proves the Python parent survived `subprocess.run`; the **Godot import child** returned `-9` to Python, after which Python deliberately returned 45. That is consistent with a child-local kill (kernel/resource limit or engine-originated signal), not proof of a supervisor wall kill.

The executor documentation confirms the container is daemon-owned, not a child of the Windows CLI Job (`LINUX_EXECUTOR.md:182-185`), and that native timeout statuses remain diagnostic failures (`:197`).

## Raw S134/S135 comparison

All four profile packets have the same bundle manifest and trusted source closure (`source_closure_sha256=9114ed69a9b8905be4681c04650fc01be26a53a164598dea92c1942ce6e4b25f`), same Godot binary hash, same profile harness hash, same exact input file hashes, and identical created command/limits. The successful and failed rows are therefore a useful nondeterminism comparison, not a source-change comparison.

| packet | elapsed (host attach) | final profile marker | container state | OOM/host timeout |
|---|---:|---|---|---|
| S134 `gt06-s134-profile-boundary-02` | 17.312 s | `HH_PROFILE_PHASE_END import -9` | PID 0, ExitCode 45 | `OOMKilled=false`, `timed_out=false` |
| S134 `gt06-s134-profile-boundary-03` | 17.718 s | import 0, readback 0 | PID 0, ExitCode 0 | clean, not timed out |
| S135 `gt06-s135-profile-boundary-03` | 18.344 s | `HH_PROFILE_PHASE_END import -9` | PID 0, ExitCode 45 | `OOMKilled=false`, `timed_out=false` |
| S135 `gt06-s135-profile-boundary-04` | 18.141 s | `HH_PROFILE_PHASE_END import -9` | PID 0, ExitCode 45 | `OOMKilled=false`, `timed_out=false` |

Evidence paths: each packet's `executor/engine-stdout.txt`, `executor/engine-host.json`, `executor/after-command-inspect-stdout.txt`, `executor/exited-inspect-stdout.txt`, `executor/result.json`, and `probe.json` under `zdoc/reviews/20260920-gt06-s134-validation-boundary/gt06-s134-profile-boundary-{02,03}` and `zdoc/reviews/20260920-gt06-s135-managed-boundary/gt06-s135-profile-boundary-{03,04}`. S135's sealed `terminal-packet-02/static-attribution.json` independently records the same boundary: import `-9`, host exit 45, OOM false, job zero/closed, and “root cause unknown.”

The S134-03 success is especially discriminating: it completed the same parse/import/readback sequence in 17.718 s under the same 19/20-second supervisor and CPU=10 limit. Thus a generic wall timeout is not sufficient to explain S135. The failed rows stop at import while the Python parent remains alive; no readback or validation marker can be attributed to them. `validation_owner.py:153-161` requires the full ordered marker sequence and rejects the partial sequence as `VALIDATION_PHASE_ORDER`; this is a derived validation rejection, not a command-lane failure.

## Attribution boundary

The strongest static candidate for the child `-9` is the inherited hard `RLIMIT_CPU=10` (`--ulimit cpu=10:10`): import can consume roughly ten seconds of CPU while taking 17–18 seconds of wall time, and the kernel's hard CPU limit is capable of ending the Godot child with SIGKILL. This is **a hypothesis, not a proven root cause**. The current artifacts do not record a raw `waitid`/`wait4` signal source or per-child CPU counters. `OOMKilled=false` and the unchanged 1-GiB cgroup configuration argue against Docker OOM as the observed sender, but do not identify the sender. An engine self-signal or another kernel/daemon condition remains possible. No evidence shows the host helper/Job or Docker watchdog sent the signal in S135.

## Discriminating next diagnostic (design only)

Do not alter the formal deadline, gate, baseline, or retry an identical preflight. For a fresh diagnostic run ID and one container at a time:

1. Keep the exact input/toolchain and supervisor, but replace only the diagnostic profile wrapper with a recorder that launches each phase as `Popen`, captures raw `waitid`/`wait4` status, wall span, `resource.getrusage(RUSAGE_CHILDREN)` user/system CPU deltas, and `resource.getrlimit(RLIMIT_CPU)` in the child context. Record `/proc/<pid>/limits` before import and host `inspect` state/`OOMKilled`/actual exits. This preserves the fixed phase commands while adding the missing signal/counter evidence.
2. Run an A/B pair in fresh, clearly diagnostic containers: A with current CPU soft/hard=10 and wall TERM/KILL=19/20; B with only the CPU hard limit raised (for example 20) while memory, CPU quota, mounts, image and wall supervisor remain unchanged. If A returns child `si_status=9` with CPU usage at the 10-second limit and B reaches import 0/readback, that discriminates RLIMIT_CPU. If the child is `SIGKILL` below the limit in both A and B, CPU limit is exonerated and engine/kernel/daemon attribution remains open. A wall-deadline control may use a deliberately shorter diagnostic timeout to demonstrate that a supervisor kill removes the phase-end marker; do not treat that control as acceptance evidence.
3. Require host-captured exits and teardown for each lane (`docker wait`, `inspect`, Job zero/closed, owned removal), preserve raw stdout/stderr and source/evidence hashes, and do not run a coupled repair or formal benchmark until the boundary has changed and the sender is observed.

This design is intentionally bounded and diagnostic. It does not claim a pass, no-leak result, or root cause from the existing S134/S135 packets.
