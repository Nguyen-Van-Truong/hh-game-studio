# GT06 S137 — bounded import-boundary differential design

**Authority:** 0 (design handoff only; no acceptance, critic signature, or plan
state change)  
**Date:** 2026-09-21 (Asia/Saigon)  
**Scope:** attribute the existing S135 `import -9` boundary using read-only
executor/environment evidence before any new GT06 run.  
**Current status:** proposed; this document was written without starting
Godot, Docker, tests, or a benchmark.

## Guardrails

The next step must keep the current GT06 gate, the 20-second executor deadline,
the 19-second in-container supervisor deadline, source closure, profile,
binary/image pins, and resource envelope unchanged. It must use a fresh
diagnostic run identifier if a run is eventually authorized; neither
`gt06-s135-profile-boundary-03` nor `-04` may be reused. It must not edit
`studio/`, the plan TXT, the installed binding, or the fixture/profile. It is a
diagnostic lane only: no publication, ACK, F13/F14 dataset, PASS, no-leak, or
root-cause claim can result from it. Keep one owned container/process tree at a
time and remove only that owned container after evidence is captured.

## What the current evidence establishes

The two S135 probes are a useful controlled pair:

* `zdoc/reviews/20260920-gt06-s135-managed-boundary/gt06-s135-profile-boundary-03/probe.json`
  and the corresponding `-04/probe.json` have the same source closure
  `9114ed69a9b8905be4681c04650fc01be26a53a164598dea92c1942ce6e4b25f`, profile
  harness SHA `efde8370a6157ed2f66544ee13b82ee2556b59130f5306e9e0774ed0e3be79a5`,
  and bundle manifest SHA
  `59d82989f9590b0842ae87a74fff6aa20db8cde6ddc0039dfa0824d0fc745e96`.
* Each `executor/engine-stdout.txt` records `parse 0`, reaches
  `HH_PROFILE_PHASE_BEGIN import`, and ends with
  `HH_PROFILE_PHASE_END import -9`; no readback marker is present. The elapsed
  host times are 18.344 s and 18.141 s, and both Docker waits/host starts end
  with exit 45. This places the failure after container startup and parse, at
  the import child boundary, but does not identify who delivered SIGKILL.
* `-03/executor/create-argv.json` and
  `-03/executor/created-inspect-stdout.txt` pin the same image
  `sha256:581429e3df12d76e6af4be5ab7d0e7fc2013eb57dc23d2de691411c8efdbb970`,
  read-only/no-network/private-IPC configuration, `1g` memory, `1` CPU,
  `pids-limit=64`, and `--ulimit cpu=10:10`. The PID-1 command execs the pinned
  `/usr/bin/timeout` (`5ef0eaaaa4220593add7716aad74da927ca3bb10605e964330de64fecc3ef15e`) with `--signal=TERM --kill-after=1s
  19s`, then runs the unchanged Python phase driver.
* `-03/executor/after-command-inspect-stdout.txt`, `exited-inspect-stdout.txt`,
  `result.json`, and `wait-stdout.txt` show a normal exited container with
  `ExitCode=45`, `Error=""`, `Dead=false`, `Paused=false`, and
  `OOMKilled=false`; Docker start was not host-timeouted, both stream readers
  reached EOF, and the job evidence reports `zero_observed=true`, `closed=true`,
  `active_count=0`. This rules out an observed Docker OOM and an observed
  leftover, but a child SIGKILL or an RLIMIT_CPU kill is not represented by
  `State.OOMKilled`.
* The packet-level conclusion is already recorded in
  `terminal-packet-02/analysis.json` and `static-attribution.json`: diagnostic
  only, root cause unknown, no identical preflight retry. The plan's current
  action at lines 66–71 and 141–149 is static phase/environment attribution
  followed by a changed-boundary diagnostic.

The timing also matters. From `created-inspect-stdout.txt` to
`after-command-inspect-stdout.txt`, container creation is about 1.8 s and the
started-to-finished interval is about 17.7 s, while the inner wall deadline is
19 s. Therefore the observed `-9` is not enough to call the 19-second timeout;
the fixed 10-second CPU ulimit is a candidate explanation that requires
measurement, not a conclusion. `OOMKilled=false` cannot disprove that
candidate.

## Differential diagnostic (future, bounded, not executed here)

### D0 — read-only static preflight

Before authorizing another container, make one small derived table from the
two existing probe directories. Compare, without rewriting them:

1. source/profile/bundle hashes and the full `create-argv.json` command;
2. image digest, Docker context/endpoint, mounts, user, CPU/memory/pids and
   all ulimits from `created-inspect-stdout.txt`;
3. container `Created`, `StartedAt`, `FinishedAt`, `ExitCode`, `Error`,
   `OOMKilled`, and `Pid` from the pre/start/after/exited inspect captures;
4. phase-marker order, host elapsed/timeout fields, `docker wait` value,
   stream EOF/error fields, and job-object snapshots from `probe.json` and
   `result.json`.

The output should be a derived `static-diff.json` with a decision of
`IMPORT_CHILD_OR_LIMIT_UNKNOWN`, never `PASS`. Any mismatch in the supposedly
identical pair, missing inspect/exit evidence, or stale hash is a stop condition
and means no new run.

### D1 — one exact-profile run with an external observer

Only after D0 is clean, run the existing `profile-validate` command once under
a new run/command ID. Do not alter the executor or profile. Arm a host-side,
read-only observer before `docker start --attach` and collect only the owned
container (by its fresh `hh.gt03.owner` label):

* Docker event records for `create`, `start`, `kill`, `oom`, `stop`, and `die`,
  with daemon timestamps;
* pre-start and post-exit `docker inspect` state/config, including the exact
  `Cmd`, `HostConfig.Ulimits`, `State`, and timestamps;
* bounded `docker stats --no-stream` samples while the container is running,
  plus `docker top` process snapshots if the daemon exposes them; and
* the existing attached stdout/stderr, actual host exit, `docker wait` exit,
  and job/handle evidence. The observer itself has a hard 30-second collection
  cap and must leave no process or container behind.

The observer is evidence collection, not a second engine worker. If any
required event, actual exit, or process/resource sample is unavailable, record
`DIAGNOSTIC_INCOMPLETE` rather than infer a cause.

Interpret the pair using these fail-closed rules:

| Observation in the exact-profile run | Narrow attribution | What it does not prove |
|---|---|---|
| No `parse 0` marker, or container `die/kill/oom` precedes any engine marker | container/image/startup boundary | not an engine root cause |
| `parse 0` and `BEGIN import` appear; a Docker `oom` event or `OOMKilled=true` accompanies container death | container memory kill | no source fix or acceptance |
| `parse 0`, `BEGIN import`, then `END import -9`; no Docker `oom/kill` event; process snapshot/counters end at the child while PID 1 remains long enough to print the marker | Godot import child/per-process limit boundary | not whether CPU, seccomp, or Godot itself caused it |
| Same marker sequence and the child user+system CPU time approaches the fixed 10-second RLIMIT region (cross-check total cgroup `cpu.stat`), with no container kill/OOM | strong CPU-limit attribution | still diagnostic; do not change the limit |
| Container dies near the fixed 19-second supervisor deadline with timeout/TERM evidence | supervisor deadline boundary | not a workload leak |

`docker stats` alone is insufficient to distinguish CPU RLIMIT from a Godot
internal kill. The required report must retain raw samples and state that
`resource-pressure-unresolved` when the signal source is absent.

### D2 — inert envelope control (separate diagnostic lane)

In the same diagnostic window, and never concurrently with D1, run one
short-lived **non-Godot** control using the same image, mounts, user, supervisor,
resource limits, and cleanup ownership. Its ephemeral command only emits a
start/end sentinel and exits; it is not installed under `studio/`, is not part
of the source/profile closure, and is not an acceptance run. Use the same
external observer and the same fixed timeout values.

* Control cleanly reaches its end sentinel with no Docker kill/OOM while D1
  repeats `import -9`: container startup/supervisor is exercised successfully,
  so the remaining boundary is specific to the Godot import child or its
  per-process resource use. This still does not identify the internal cause.
* Control receives the same container-level death or fails before its sentinel:
  classify the envelope/supervisor as suspect and stop; do not edit Godot or
  retry the profile.
* Control is clean but D1 lacks observer events or actual exits: classify
  `DIAGNOSTIC_INCOMPLETE`, not Godot workload.

This control changes no gate, timeout, source file, profile, or pinned binary;
it exists only to answer the startup-versus-workload question. The observer
and control must be captured in a fresh, authority-0 review directory with a
manifest and source/profile hashes. They must never be folded into F13/F14.

## Stop/hand-off criteria

Stop after D0 if the pair is not byte/config identical. Stop after D1/D2 if
there is no actual host exit, event/process evidence, or owned-tree cleanup.
Do not run the managed repair/replay, formal GT06 campaign, or coupled RSS
campaign from an unresolved boundary. A result may be handed to the
coordinator as one of `STARTUP_BOUNDARY`, `IMPORT_CHILD_OR_CPU_LIMIT`,
`SUPERVISOR_DEADLINE`, or `DIAGNOSTIC_INCOMPLETE`; only a future source repair
and the existing GT06 verification/critic gates can change product state.
