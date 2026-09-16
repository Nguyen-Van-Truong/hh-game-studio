# S49 Linux executor implementation cross-review

AUTHORITY=0. IMPLEMENTATION_REVIEW_ONLY=1. ACCEPTANCE_VERDICT=NONE.
PLAN_TICK=NONE. CONTAINERS_STARTED_BY_THIS_REVIEW=0.
Date: 2026-09-17, Asia/Saigon. Git baseline: `e09f7806a6e3198e82c4ac1dd42dffd342531ef5`.

One actionable P2 lifecycle finding was reproduced with pure native-failure
injection. No additional admission/supervisor escape was established in this
bounded review. This is neither sandbox acceptance nor a claim that remaining
resource/security gaps are closed.

The reviewed source is the worker's frozen snapshot under
`20260917-gt03-s49-executor-probes/source/studio/`. The coordinator took live
executor write ownership during review to add fixed complete-profile modes.
Those later edits and their execution/materialization boundaries are outside
this report. All code line references below refer to this preserved snapshot.

| Reviewed file, relative to snapshot `studio/` | SHA256 |
| --- | --- |
| `godot-addon/linux_executor.py` | `a38367a345372eddc32417a359083a875eea3ee06a4360b3d0ca95e772724fe1` |
| `godot-addon/LINUX_EXECUTOR.md` | `265d2f8a350a701bf4051162629218fdc746a40a863287aea9373cb1f351ec25` |
| `godot-addon/validator-toolchain.lock.json` | `de8d1c9e31e4326d0608d2a7fa0d69d571bc11ef709c447e924b77b6901a0114` |
| `tests/godot/test_linux_executor.py` | `4b1fd9f275062195d3524b728f51ae5bf454ec6365ab612ce88d35cdb95acdde` |
| `build/bootstrap/run_fixture.py` | `ea522450acc46f90be5e2a7b9257e73ce8b619948105b2c9073aac1f881c7328` |

## F1 — P2: failed native Job close can report clean and lose cleanup ownership

**Locations:** `godot-addon/linux_executor.py:376`, within cleanup lines
369–386; cleanliness predicate lines 399–403 and next-run hold check line 486.
The invoked pinned helper is `build/bootstrap/run_fixture.py:207–209`.

`_cli` calls `owned._close_job(job)` and then proceeds as though Job ownership
was released. That pinned helper invokes `kernel.CloseHandle(handle)` without
checking its BOOL result. If native close returns zero, the live handle is
discarded from executor bookkeeping. `_INCOMPLETE_CLI_HOLDS` retains only
unfinished reader/pipe ownership, so fully drained streams do not retain this
failed Job owner. `_cli_clean` has no close-success requirement.

This review reproduced the failure using the **actual pinned helper**, a fake
kernel whose `CloseHandle` returns zero, a completed fake CLI process with
normal EOF on both streams, and a mocked zero Job active count. Observed result:

```json
{
  "native_close_return": 0,
  "native_close_calls": 1,
  "cli_clean": true,
  "incomplete_cli_holds": 0,
  "exit_code": 0,
  "job_active_count": 0,
  "stream_reader_eof": [true, true],
  "stream_reader_errors": [null, null]
}
```

The native failure was **injected**, not an observed Windows kernel failure;
no real Docker process or leaked real handle was created by the repro. The
code path and helper's dropped return value are concrete. It can leak a Job
handle while allowing a clean diagnostic result and further requests. If an
active-count/termination uncertainty also occurs, the same unchecked close
path fails to preserve the exact native cleanup owner. The repro establishes
the zero-active-count case; it does not assert an observed escaped container.

Minimal repro construction, after loading the frozen executor as `executor`:

```python
runner = executor._owned_runner()  # verifies and loads the pinned helper
class Kernel:
    def CloseHandle(self, handle):
        return 0
job = (Kernel(), 123)
# Popen is replaced by a completed fake process with BytesIO stdin/stdout/
# stderr, returncode=0, poll()=0, wait(timeout)=0. No process is launched.
with patch.object(executor.subprocess, 'Popen', return_value=fake_process), \
     patch.object(runner, '_job_for_process', return_value=job), \
     patch.object(runner, '_job_active_count', return_value=0):
    row, _ = executor._cli(runner, ['version'], temporary_output, 'close-failure')
assert executor._cli_clean(row) is True  # undesired current behavior
assert executor._INCOMPLETE_CLI_HOLDS == []
```

**Requested implementation:** add an executor-owned checked Job close without
changing the accepted bootstrap/core. Record a failed close as an uncertain
host lifecycle result, retain the exact `(kernel, handle)` cleanup owner,
reject clean status, and hold subsequent runs until explicit safe cleanup.
Handle exceptions in the cleanup path without dropping that owner. Add a
regression against native BOOL failure, not only a helper that raises. Cover
both settled zero-active and failed/unknown active-count paths; a follow-up
close may be attempted only on the same retained owner.

The finding was sent to the coordinator and the original executor worker.
The worker confirmed no contrary evidence and did not edit the frozen source.
Any coordinator fix requires its own new source hash and regression evidence;
this report does not silently transfer a verdict to it.

## Evidence read and checks actually performed

This reviewer ran the existing pure executor suite in a child process with
`subprocess.run(..., timeout=30)`: actual exit 0, **18 tests**, 0.768 seconds.
Command: `python -B -m unittest discover -s <studio/tests/godot> -p
test_linux_executor.py -v`, with `studio` as cwd. All five reviewed source
hashes were captured before that run and matched the worker's frozen snapshot.
The suite uses mocked Docker/lifecycle operations and bounded temporary files;
it does not establish actual sandbox enforcement. The additional failure
injection above ran separately in the review process and completed normally.
No executor source, lock, test, core or plan file was written by this review.

The matching-source actual host-death evidence is **host-death-05**, not -03.
Read inputs include its `probe-result.json`, passive observer output, the
probe driver and actual inspect/CLI records. It records:

* Exact recorded container
  `20b3734457936efc072b91559f2de56667e47fe1b787a55b83eba65e01b7929e`
  running before host termination; host Job active count 0 and actual host
  exit 2 after termination.
* Another process denied with `EXECUTOR_ADMISSION_BUSY`, without a second
  container ID. The next engine is created only in the later recovery run.
* Passive attach with `--sig-proxy=false`, EOF on both streams, native exit
  124, no observer timeout and no host Job processes remaining. The retained
  output contains `S49_IDLE_BODY_AFTER_HOST_DEATH`.
* Container start `2026-09-16T17:33:02.401975026Z`, host kill at
  `17:33:04.082027+00:00`, finish `17:33:09.674940265Z`: recorded lifetime
  **7.272965 seconds** for the configured seven-second TERM/eight-second
  maximum supervisor. Final daemon state is stopped, PID 0, exit 124.
* Recovery identifies that exact orphan, observes stopped state, removes it,
  proves its ID missing, and then completes a new clean diagnostic run and
  owned removal. The API still reports `public_ack=false`,
  `sandbox_acceptance=false` and `host_death_acceptance=false`.

`host-death-01` and `host-death-04` retain incomplete probe results and are not
passing proofs. The worker identified -04 as a probe race between persisted
`start_pending` and actual Running state; -05 performs an actual running-state
check and includes preexisting-orphan recovery. Earlier -02/-03 successful
observations remain historical, not substitutes for the final source binding.

The focused supervisor probes were also read as scoped observations:
`pid1-stop-ptrace-01` shows Yama 1, PID 1 still sleeping after stop/kill/tstp
attempts, ptrace denied with errno 1, `/proc/1/mem` denied with errno 13, then
exit 137 and verified removal. SIGALRM and SIGCHLD/SIGCONT flood probes show
bounded exits and removal. These are purpose-built Python supervisor probes,
not complete Godot hostile-project or final-source publication tests; their
scope must not be enlarged by combining favorable JSON fields.

## Boundaries that remain explicit

The inspected admission path checks the fixed daemon endpoint, exact prior
name/ID/image/owner label, stopped PID-zero state and verified removal before
new create. Missing ambiguous create requests and unknown context-labelled
containers deny admission; labels alone do not permit deletion. A failed mutex
release is held separately. This review found no additional concrete bypass
of those checks in the frozen source.

The supervisor executes as namespace PID 1 with fixed timeout and Yama
preflight; command/config/mount/resource properties are checked before start.
Host CLI EOF, cap and process state are checked independently of child claims.
The F1 cleanup defect remains distinct from the successful ordinary teardown
and host-death observations.

Existing documented exclusions remain material: no protected host path/custody
against a concurrent same-user attacker; no aggregate retained-evidence quota;
incomplete OOM, IPC/PTY/inode/shared-memory and task-exhaustion coverage; no
whole-daemon quota; no trusted attribution of candidate-generated output; no
public save/publication/restart authority. The complete eleven-file profile,
new fixed harness/modes and their closed dependency proof were not reviewed
here. No acceptance, plan tick or public availability follows from this report.
