# S70: durable campaign execution and nested ownership

GT06 remains IN_PROGRESS. No interrupted prefix, worker report, scheduler
dispatch, diagnostic or unit count is an acceptance verdict.

## Why the S69 campaign could not finish

`campaign01-forensics.md` records one completed warm-up sample, zero measured
samples, and no completed run. Host/editor exits and cleanup are absent after
the tool execution disappeared. Current process absence does not repair this
evidence. Earlier launch status RUNNING is historical.

The old editor stderr also contains a startup RD-child creation error. Stock
Godot still attempts this capability probe while using OpenGL; adding renderer
flags does not disable it. The old parent Job already counted two host and two
editor processes against its four-slot aggregate limit. The editor's RD probe
needs a fifth parent slot. The revised declared parent profile reserves two
host slots plus the unchanged four-slot editor Job, totaling six. CPU, RAM,
wall, workload, latency and growth thresholds remain unchanged. Native A/B
diagnostics are required to substantiate the static explanation.

The bounded A/B diagnostic has now run under the same frozen code:
`gt06-nested-owner-legacy-01` reproduced the RD startup error and correctly
failed clean-log validation; `gt06-nested-owner-composed-01` passed a complete
native cycle with empty stderr. Both obtained actual host/editor target and
helper exits0, closed/zero Jobs and released wrapper handles; controller exit1
for the legacy diagnostic represents its expected log failure. The composed
diagnostic took19.094s. This is a scoped configuration correction demonstrated
on this host, not a full benchmark or a claim about every Windows/GPU setup.
The recorded active-count peaks are raw accounting observations, not a census
of distinct simultaneously runnable PIDs or a replacement for queried limits.

`NativeLog.poll` now rejects nonempty stderr at first observation. Its existing
final clean-log requirement remains; a known-invalid startup no longer consumes
the whole benchmark deadline.

## Demand-only launcher

`studio/tests/replay/campaign_task.ps1` registers only a uniquely named task
under the current user's interactive identity, with no password, elevation,
triggers, automatic retries or logon/reboot restart. A hidden Pythonw supervisor
is the fixed action. The task remains discoverable in Task Scheduler.
Normal priority6, one-instance policy2 and a finite deadline are checked by
reading back the registration before dispatch. Probe deadline is two minutes;
whole-campaign deadline is24 hours. Original per-run deadlines still apply.
The current interactive user session must remain available for the GUI editor.

The supervisor invokes the existing campaign in its own process, retaining the
checked per-run Job hierarchy. It does not add another process inside the
editor's four-slot Job. Fixed-slot Stop still latches; no stopped campaign is
silently restarted. Dispatch is not completion. `return.json` explicitly says
the supervisor's actual exit has not yet been observed; terminal scheduler
status supplements the inner native exit/ownership records.

Source/request/XML hashes, task principal/action/settings and instance GUID are
recorded. Status/delete address only the exact derived task. Delete refuses a
running instance, and raw records survive deletion.

## Executed launcher probes

- `gt06-s70-task-probe-01`: launcher preparation failed before registration due
  to multiple `Get-Command python.exe` results being treated as one path. Raw
  failure remains. Select the first actual command resolution. An earlier
  missing-task lookup also exposed PowerShell translating the exact not-found
  HRESULT into FileNotFoundException; the fix matches only that HRESULT and
  does not mask access denied.
- `gt06-s70-task-probe-02`: demand dispatch returned; the scheduler-owned
  process continued, then finished a real12-second owned child with verified
  actual exit0, closed/zero Job and released wrapper handle. Supervisor returned0,
  scheduler terminal result0, no active instances. Current-process priority32
  (NORMAL) and process creation time were captured. This proves separation from
  the returned launch command, not yet survival across a later chat turn.
- `gt06-s70-task-stop-01`: bound Stop was published through the existing channel.
  It produced BENCHMARK_STOPPED, closed/zero Job and released wrapper handle.
  Supervisor returned1 and terminal scheduler result1. This is successful
  cancellation evidence, not natural native exit0 or benchmark PASS.

Both completed task registrations were deleted after checking terminal status
and ownership proof. Raw data remains under `studio/.local/reviews/` and the
exact probe source is retained in `probe-source-01/`. Later supervisor edits
must not be assigned to those earlier source hashes.

An explicitly numbered launch is now supported: `-LaunchNumber 2` / Python
`--launch-number 2` creates a separate task and supervisor evidence directory.
The campaign data root stays the same. Unchanged-source completed-run reuse,
failed-attempt cleanup checks and the campaign Stop latch still apply. There
is no automatic retry. Exact task slots1–99 are checked before dispatch; this
preflight is not an atomic lock, so coordinator launch calls remain serialized.
The launch2 probe for `gt06-s70-task-probe-02` also passed actual exit0 and
checked cleanup, with terminal scheduler result0; its task was then deleted.
Earlier launcher probes retain their original source snapshots and hashes.

`../20260918-gt06-s70-units-01/` records the affected owner/Stop/campaign/assembly
and scheduler-request tests: 73/73 passed, no skips,17.551s. The source list binds the launcher and diagnostic
drivers too. Actual child/helper exits0, owned tree verification and unchanged
source are required; these counts supplement the earlier full suite.

`evidence-inventory.json` binds the six retained diagnostic roots and selected
small captures are copied under `captures/`. Full raw data remains local;
copied summaries do not replace it or imply a final GT06 review closure.

## Full campaign startup correction

Checkpoint `a007b21` was dispatched as `gt06-s70-campaign-01`. The scheduler
supervisor exited1 after1.422s; its child rejected `CAMPAIGN_SOURCE_CHANGED`
before creating a native project. The imported-module inventory contained
`run_campaign_task.py` only in the parent, producing unequal entrypoint maps.
The actual target/helper exits1, closed/zero Job and released process handle
are retained, along with scheduler terminal1. The finished task was deleted;
the failed source/prefix remain and contribute no benchmark samples.
`campaign01-failure-inventory.json` binds both raw roots; selected original
captures are copied under `captures/`.

The campaign now unions its imported dependency closure with both Python
entrypoints, the PowerShell launcher and `contracts/perf-collector.schema.json`
(loaded by the performance module). Exact parent/child equality remains.
Separate-interpreter regression reproduces the two import environments and
checks matching maps; changes to any fixed launcher/schema source are rejected.
`../20260918-gt06-s70-units-03/` records75/75 affected tests in19.106s, no skips,
actual child/helper exits0, verified tree cleanup and unchanged source. The
earlier75/75 in `-units-02` predates adding the schema; counts are not additive.
Because source changed, campaign02 must use a fresh root. No completed run is
discarded: campaign01 never reached a batch.

The fixed source was committed at `9bc28b6`; campaign02 was dispatched at
2026-09-17T18:25:28Z. `campaign02-launch.json` records the01:27:07 local
observation: running scheduler instance, clean host/editor stderr and the first
complete warm-up batch with six byte-verified artifact references. All49 source
files match live disk, frozen copy and Git. This is not a full run or a measured
sample; actual terminal captures and the full dataset remain required. Requery
the exact task in `campaign-operations.md` when resuming rather than treating
this launch record as current status. The three preparation reports are not
final independent acceptance verdicts.

## Remaining work

Changed-driver verification and nested native ownership proof are recorded.
Freeze the corrected source and launch the exact full campaign. Keep all failed prefixes and
resume only complete runs under unchanged source/profile/workstation, with
verified cleanup for previous failed attempts. No heavy native/test work runs
concurrently with measured batches.

`critical-path.md` maps final GT06 evidence and later prerequisites. After full
measurement, build the final requirement/artifact closure and obtain two fresh
independent reviews. GT07–10 remain gated; physical Android is mandatory at
GT08. HH World is a separate plan after GT10. No reliable whole-plan ETA exists.

## Primary references

Microsoft documents passwordless registration under the caller's own
interactive identity and permits the lower privilege run level.
[Task security contexts](https://learn.microsoft.com/en-us/windows/win32/taskschd/security-contexts-for-running-tasks).
The launcher uses a finite execution limit and one-instance policy, and sets
normal priority explicitly because the scheduler default is below normal.
[ExecutionTimeLimit](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-executiontimelimit),
[MultipleInstances](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-multipleinstances),
[Priority](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-priority).
Windows accounts nested descendants in their parent Job, so the outer limit
must cover the declared child budget plus its own host processes.
[Nested Jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs).
