# S49 executor lifetime and admission diagnostics

AUTHORITY=0
PUBLIC_ACK=false
SANDBOX_ACCEPTANCE=false
FORMAL_GT03_ACCEPTANCE=false
SOURCE_HANDOFF=coordinator owns subsequent executor/profile edits

This snapshot adds a container-resident deadline and cross-process admission
to the internal three-file Linux diagnostic executor. Its scoped probes
observed host-runner death, an idle script continuing inside the orphaned
container, native deadline exit, denial of a concurrent caller and exact-owner
recovery before the next engine. These observations do not establish complete
sandbox acceptance or trusted validation attribution.

## Exact source and test identity

The [source freeze](source-freeze.json) records five copied source files plus
the three probe scripts. The copy was made after host-death-05; executor source
remained unchanged during that run. Current workspace source may now differ
because the coordinator has taken ownership for additional profile modes.

| Frozen file | SHA256 |
| --- | --- |
| `source/studio/godot-addon/linux_executor.py` | `a38367a345372eddc32417a359083a875eea3ee06a4360b3d0ca95e772724fe1` |
| `source/studio/godot-addon/LINUX_EXECUTOR.md` | `265d2f8a350a701bf4051162629218fdc746a40a863287aea9373cb1f351ec25` |
| `source/studio/godot-addon/validator-toolchain.lock.json` | `de8d1c9e31e4326d0608d2a7fa0d69d571bc11ef709c447e924b77b6901a0114` |
| `source/studio/tests/godot/test_linux_executor.py` | `4b1fd9f275062195d3524b728f51ae5bf454ec6365ab612ce88d35cdb95acdde` |
| `source/studio/build/bootstrap/run_fixture.py` | `ea522450acc46f90be5e2a7b9257e73ce8b619948105b2c9073aac1f881c7328` |

[Pure-test evidence](pure-tests.json) captures actual exit 0 and 18 tests run
against that copied source. Tests cover command/config rejection, stream EOF
failure, lost create reply, owned output-cap cleanup, durable-owner validation,
unknown-container denial, unresolved create ambiguity, recorded-orphan cleanup
and native mutex release/close failure retention. They do not start an engine.

## Deadline prerequisite and focused hostile probes

The existing pinned image
`sha256:581429e3df12d76e6af4be5ab7d0e7fc2013eb57dc23d2de691411c8efdbb970`
contains GNU coreutils timeout 9.1, 48632 bytes, SHA256
`5ef0eaaaa4220593add7716aad74da927ca3bb10605e964330de64fecc3ef15e`.
The [trusted pin probe](pin-01/engine-stdout.txt) observed this hash/version
and Yama ptrace_scope 1; its container exited 0 and was removed. No image pull,
installation, daemon configuration change or accepted toolchain-lock change
was performed.

The fixed isolated Python preflight checks the timeout hash, PID 1, UID 65532
and Yama scope in `{1,2,3}`, then execs timeout into the same PID 1. Timeout
receives fixed TERM/kill-after arguments; Godot receives only the existing fixed
parse/import command. No caller argv, environment, image, entrypoint or mount
extension was added. The configured deadline is TERM after
`max(1, timeout_seconds-1)`, then KILL one second later, at most 20 seconds plus
kernel scheduling latency. Host attachment has two seconds of observation
grace. Setup/recovery are separately bounded CLI operations.

Linux PID namespaces protect init from child stop/kill signals and terminate
the namespace when init exits. Coreutils does not reset its final kill alarm
on subsequent handled signals. These facts support the design but do not
substitute for the local probes.
[Linux PID namespaces](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html),
[coreutils 9.1 implementation](https://github.com/coreutils/coreutils/blob/v9.1/src/timeout.c).

| Probe | Observed result |
| --- | --- |
| [PID1 stop and tracing attempts](pid1-stop-ptrace-01/result.json) | Child sent SIGSTOP/SIGKILL/SIGTSTP; PID1 remained sleeping. PTRACE_ATTACH returned EPERM and `/proc/1/mem` open returned EACCES. TERM-ignoring idle child ended native 137 after about 5.14 seconds for TERM4+KILL1; owned removal verified. |
| [Repeated SIGALRM](pid1-alarm-flood-01/result.json) | Signals caused early native 137, rather than extending the deadline; owned removal verified. |
| [Repeated SIGCHLD/SIGCONT](pid1-chld-flood-01/result.json) | Native 137 after about 5.11 seconds for TERM4+KILL1; owned removal verified. |

Default Docker seccomp permits ptrace/process_vm operations on newer kernels;
the tracing result must not be attributed to seccomp alone. Restricted Yama is
an explicit checked prerequisite. The host administrator remains trusted and
the project cannot change its read-only sysctl with all capabilities dropped.
[Moby default profile](https://github.com/moby/profiles/blob/main/seccomp/default.json),
[Linux Yama](https://docs.kernel.org/admin-guide/LSM/Yama.html).

## Matching-source host-death and admission evidence

[host-death-05/probe-result.json](host-death-05/probe-result.json) is the final
matching-source run. An independent bounded attach observer watched the same
owned container; it did not start another engine.

- The owning Windows Job was killed 1.680 seconds after Docker's recorded
  start, with actual Windows exit 2 and settled Job active count zero.
- The fixture waits three seconds before printing its idle-body marker and
  then sleeps repeatedly. The independent attach captured that marker while
  the original runner was gone. Child text is a fixture observation, not a
  validation ACK.
- The container stopped itself with native exit 124, PID zero, OOMKilled false
  and lifetime 7.272965 seconds for TERM7+KILL1. The observer did not kill it.
- A separate concurrent host process waited for admission and returned
  `EXECUTOR_ADMISSION_BUSY`, with no container ID.
- The next run read the durable name/image/full-ID record, observed and removed
  that exact stopped orphan, required an empty reserved-label inventory, then
  started its own engine. That engine exited cleanly, was removed, and the
  owner record was cleared. No foreign-container cleanup or prune occurred.

The mutex name is global for the fixed Docker context, while the bounded
owner record is under the current account's LOCALAPPDATA. Unknown labelled
containers and other-account orphans deny admission; their labels alone do
not authorize cleanup. Missing objects after an unresolved create reply retain
ambiguity and deny later runs. The record is not a custody guarantee against
a malicious process with the same host account.

The actual command, from the workspace at the frozen source above, was:

```text
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s49-executor-probes/probe_host_death.py 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s49-executor-probes/host-death-05
```

The probe imports the workspace executor; a future reproduction must bind its
source to the desired freeze and use a fresh output directory. Re-running it
against later profile source does not reproduce this source identity.

Historical attempts remain intact: host-death-01 rejected a CRLF project
template before container creation; -02/-03 observed the behavior on earlier
source; -04 stopped on a probe race between persisted start_pending and actual
Docker Running. Its durable owner was safely reconciled by -05 before the
final experiment. None is silently relabelled as the final run.

## Remaining gaps and handoff

The read-only critic identified an additional ownership gap after source
handoff: `_cli()` still delegates Job closing to accepted bootstrap
`_close_job`, which ignores native CloseHandle failure. This snapshot has no
proof that a failed Job close retains the handle or prevents a clean result.
The coordinator owns the executor-side repair; the accepted bootstrap must
remain pinned. Mutex failure handling was repaired here, but that does not
close the separate Job-handle finding.

Admission bounds this executor's simultaneous containers, not all Docker
users, the whole VM, input snapshots prepared before admission or accumulated
host evidence. Aggregate retention, complete IPC/PTY/inode/shared-memory/OOM/
task-exhaustion coverage, mutable host custody and trusted engine attribution
remain open. Runtime readback/publication integration is outside this snapshot.
Both public ACK and sandbox acceptance stay false. No source commit or plan
tick was performed by this lane.
