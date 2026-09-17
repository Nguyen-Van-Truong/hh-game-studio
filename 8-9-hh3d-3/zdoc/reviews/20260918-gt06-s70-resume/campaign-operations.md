# GT06 S70 campaign operations

Static handoff based on commit `a007b21f5b7f630644d45b95be7a4e83cb63e678`,
with the coordinator's later failure update. `gt06-s70-campaign-01`, launch 1,
was dispatched at `2026-09-17T18:21:53Z` and then failed before native import
with `CAMPAIGN_SOURCE_CHANGED`: the parent's dynamically imported source
closure included the scheduler wrapper, while the child's did not. The
coordinator reported checked closed/zero owner cleanup, released wrapper
handle and terminal scheduler result1. This is a failed attempt, not RUNNING
or a completed benchmark. The coordinator is fixing a shared fixed campaign
entry-source union. That driver change requires fresh campaign ID
`gt06-s70-campaign-02`; launch 2 of campaign01 cannot repair the source mismatch.
Coordinator update: source fix `9bc28b6` was dispatched as campaign02 at
`2026-09-17T18:25:28Z`; the current source closure is
`21a17b2a350160efb17950979adada0a2b3e12dbd95e12158833acbe9f233aa0`
(49 files). This is startup evidence, not a completed benchmark. Recheck live
task status when resuming; this note is an observation at launch time.

This handoff did not query the task or execute any command below. Recheck the
final fixed source checkpoint and actual launch receipt in the later turn.
GT06 remains IN_PROGRESS; no acceptance claim is made here.

## Locations and one-shot inspection

Use the same interactive Windows user and console Python resolution as the
recorded task registration. Run these setup assignments once in PowerShell:

```powershell
$studio = 'D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio\8-9-hh3d-3\studio'
$campaignId = 'gt06-s70-campaign-02' # Recheck live task status before any action.
$launchNumber = 1
$suffix = if ($launchNumber -eq 1) { '' } else { '-launch-{0:D2}' -f $launchNumber }
$launcher = Join-Path $studio 'tests\replay\campaign_task.ps1'
$campaignRoot = Join-Path $studio ('.local\reviews\' + $campaignId)
$supervisor = Join-Path $studio ('.local\reviews\' + $campaignId + '-supervisor' + $suffix)
$python = (Get-Command python.exe -CommandType Application | Select-Object -First 1).Source
```

Read the exact task once when resuming a later turn or reaching a meaningful
boundary. Do not treat old launch receipts as live state, or use a polling loop.

```powershell
& $launcher -Command status -CampaignId $campaignId -LaunchNumber $launchNumber
Get-Content -LiteralPath (Join-Path $supervisor 'stdout.txt') -Tail 8
Get-Content -LiteralPath (Join-Path $supervisor 'stderr.txt') -Tail 12
```

Status validates the stored request, XML, action, principal and task settings.
It does not revalidate current source bytes or prove child cleanup. State 4 is
running, 2 queued, 3 ready, 1 disabled, 0 unknown; retain the instance GUID and
last-run time. An empty instance list and terminal last-task result supplement
the supervisor return record. `scheduler_engine_pid` is not a host/editor PID.
Do not infer success from result 0 until the matching launch actually ran and
has terminal evidence. The script's `exit` makes a separate shell invocation
preferable if the caller is itself a long-lived PowerShell script.

Inspect only the bounded 30 attempt slots to locate progress and Stop latches:

```powershell
0..9 | ForEach-Object {
    $runIndex = $_
    1..3 | ForEach-Object {
        $attempt = Join-Path $campaignRoot ('run-{0:D2}-attempt-{1:D2}' -f $runIndex, $_)
        if (Test-Path -LiteralPath $attempt) {
            [pscustomobject]@{
                Attempt = Split-Path $attempt -Leaf
                Context = Test-Path -LiteralPath (Join-Path $attempt 'context.json')
                Captured = Test-Path -LiteralPath (Join-Path $attempt 'run-capture.json')
                Failed = Test-Path -LiteralPath (Join-Path $attempt 'parent-failure.json')
                Stop = Test-Path -LiteralPath (Join-Path $attempt 'stop-request.json')
            }
        }
    }
}
```

This listing is a convenience, not the authoritative latch check: the driver
uses `lexists`, which also treats malformed links as a Stop. For an exact
observed slot, read `context.json` and the last few lines of
`host-owner/stdout.txt` and `editor-host/stdout.txt`. Host
`HH_GT06_CAMPAIGN_PROGRESS` records identify run, batch and phase; native
heartbeats identify native progress. A heartbeat or `batch-capture-NN.json`
does not prove a complete run. Preserve prior evidence, do not replay finished
runs merely to refresh their logs, and keep tests/other native lanes off the
measurement workstation while this campaign runs.

## Intentional Stop

Only execute this section when Stop is authorized. Choose an existing exact
attempt from the inspection above; the example slot must be changed if another
slot is current. Its `context.json` supplies the binding. Publication is one
exclusive temporary write, flush and Windows no-overwrite rename; it sends no
PID signal and never calls Task Scheduler Stop. A duplicate request is left
intact. If there is no attempt context yet, inspect the exact launch rather
than inventing a context or a process target.

```powershell
$attemptName = 'run-00-attempt-01' # Set to the observed exact attempt slot.
@'
import hashlib, json, os, re, stat, sys
from pathlib import Path
root = Path(sys.argv[1]).absolute()
slot = sys.argv[2]
match = re.fullmatch(r'run-(0[0-9])-attempt-(0[1-3])', slot)
if match is None:
    raise SystemExit('Invalid fixed attempt slot')
output = root / slot
def read_plain(path):
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise SystemExit('Reparse path refused')
    return path.read_bytes()
raw = read_plain(root / 'campaign.json')
campaign = json.loads(raw)
context = json.loads(read_plain(output / 'context.json'))
expected_id = f"{campaign['campaign_id']}.r{int(match[1]):02d}.a{int(match[2]):02d}"
if (campaign['campaign_id'] != root.name or context['run_id'] != expected_id
    or context['index'] != int(match[1]) or context['attempt'] != int(match[2])
    or context['campaign_sha256'] != hashlib.sha256(raw).hexdigest()
    or context['source_closure_sha256'] != campaign['source_closure_sha256']):
    raise SystemExit('Context/campaign binding mismatch')
value = {'schema': 'HH-GT06-CAMPAIGN-STOP-1', 'run_id': context['run_id'],
    'source_closure_sha256': context['source_closure_sha256'],
    'campaign_sha256': context['campaign_sha256'], 'reason': 'OPERATOR_STOP'}
target = output / 'stop-request.json'
temporary = output / 'stop-request.json.tmp'
if os.path.lexists(target) or os.path.lexists(temporary):
    raise SystemExit('Existing Stop or pending publication retained; inspect it')
encoded = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
with temporary.open('xb') as stream:
    stream.write(encoded)
    stream.flush()
    os.fsync(stream.fileno())
temporary.rename(target)  # Windows refuses an existing destination.
if read_plain(target) != encoded:
    raise SystemExit('Stop readback mismatch')
print('STOP_REQUEST_PUBLISHED', context['run_id'])
'@ | & $python -B - $campaignRoot $attemptName
```

After publication, let the checked owner perform cleanup; then inspect the
matching terminal status and failure/cleanup records. Typical active-run code
is `BENCHMARK_STOPPED`; a request seen at a boundary or in an older attempt
produces `CAMPAIGN_STOP_LATCHED`. Both are cancellation, never natural exit0
or a measurement PASS. A request against a completed attempt still latches the
whole campaign. Never remove, rename, rewrite, or ignore that Stop file to
resume. A new launch number is not an override. Any later change of intent
requires explicit owner steering and a separately scoped campaign decision.

## Manual resume after a non-Stop interruption

Resume only after all of the following are established:

1. The previous exact scheduler instance is terminal; preserve its status,
   return/failure records and source snapshot. Coordinator launch commands are
   serialized. Fixed slots 1–99 are checked before registration and dispatch,
   but those readbacks are not an atomic cross-task lock.
2. No `stop-request.json` exists in any of the fixed 10 x 3 attempt slots,
   including broken links. No intentional Stop is being worked around.
3. Source map, Python, toolchain, profile and workstation still match
   `campaign.json`. Source changes require their own campaign decision; do not
   edit pins or assign old probe source hashes to new supervisor code.
4. Completed runs retain valid `run-capture.json` and every referenced byte.
   For an incomplete run, every prior attempt has `parent-failure.json` with
   `owner_closed=true` and `owned_tree_zero=true`, backed by retained cleanup
   records. Missing proof is a blocker even when no processes remain. The
   driver permits at most three attempts per run; no partial sample splicing.

Select an unused launch number, not merely the next number guessed from an old
receipt. For the first manual resume, if launch 2 is unused:

```powershell
& $launcher -Command register-run -CampaignId $campaignId -Mode campaign -LaunchNumber 2
```

This creates `HHStudio.GT06.<campaignId>-launch-02` and
`<campaignId>-supervisor-launch-02`, retaining the same campaign root.
Use `-LaunchNumber 2` for its subsequent status/delete commands. Launch 1 has
no suffix. Both task and supervisor directory must be unused; never overwrite
an earlier claim, request, log or task to reuse a slot. A failed/uncertain Run
call is inspected, not automatically retried. Do not start the Python wrapper
directly or call `run_campaign` just to inspect state: they execute work.

The campaign revalidates completed captures and skips those full runs. It
starts a fresh pair only for the first eligible incomplete run and never
reuses partial batch data. Resumption is manual, with no trigger, restart-on-
failure, logon/reboot launch, or changed 24-hour task / 7410-second run limit.

For the known campaign01 closure failure, this resume command is inapplicable
after the driver fix. Once the coordinator has frozen and validated the fix,
its separately authorized fresh launch uses the same launcher with
`-CampaignId gt06-s70-campaign-02 -Mode campaign -LaunchNumber 1`. Preserve
campaign01's raw failure and cleanup evidence; do not alter its campaign pins.

## Terminal evidence and exact task deletion

Read the supervisor `return.json`, optional `failure.json`, stdout/stderr,
and a fresh exact task status together. `return.json` is written before
process exit and explicitly says exit is not yet observed. Result0 requires
matching scheduler terminal result0/no instances as well as the records below.
Preserve a timestamped copy of terminal status outside frozen run artifacts
before deletion; do not add files inside a captured attempt.

| Layer | Required evidence and meaning |
| --- | --- |
| Dispatch | request, task-registration, expected/registered XML and SHA256, task-start instance GUID; fixed current-user action/settings. Dispatch alone proves no workload completion. |
| Supervisor | start process identity/creation time, request/source binding, normal priority, return code, terminal scheduler result and no instances. A return record alone is insufficient. |
| Each successful run | context/source/profile/toolchain, 35 batches, child-result, host/editor captures and actual process-start/process-exit, import capture, cleanup, assembly-manifest, assembled-run and run-capture. Same host/editor identity through all 35 batches; ten fresh pairs overall. |
| Owned cleanup | Actual target/helper exits0 for successful runs; natural_tree_exit, closed/zero untainted Jobs, released wrapper handles, held_handles=0, no unexplained stdout warnings/errors or stderr. Capture schema `HH-GT06-BENCHMARK-CAPTURE-2` is required; do not fill missing v1 fields. Failed/Stop attempts instead need their truthful failure/cleanup records. |
| Whole campaign | campaign-capture references ten verified full runs; dataset and summary match strict reassembly/provenance. Summary PASS alone authenticates neither origin nor source. Five warmup + thirty measured batches per run; each batch 1000 HTTP commands and 100 native cycles. |

The existing read-only verification entry points are
`verify_run_capture` / `verify_owner_captures` in `run_benchmark_campaign.py`,
`verify_capture` in `benchmark_job.py`, and `assemble_run` / `assemble_dataset`
in `benchmark_assembly.py`. Use the frozen contexts and hashes, not caller-
supplied exit integers. After termination, the lightweight profile-only check
below can corroborate the summary; it does not replace those raw/source checks:

```powershell
& $python -B (Join-Path $studio 'tests\replay\benchmark_profile.py') --input (Join-Path $campaignRoot 'dataset.json')
```

Only after preserving terminal status and establishing owned cleanup, delete
the exact completed registration. This deletes no evidence and kills nothing:

```powershell
& $launcher -Command delete -CampaignId $campaignId -LaunchNumber $launchNumber
```

The launcher verifies the stored definition and refuses active instances;
retain its `task-deleted.json` readback. Do not delete registrations with
unresolved running/queued/unknown state, use broad `Stop-Process`, or remove
evidence. If source/Python resolution or XML binding prevents status/delete,
investigate the exact stored registration rather than bypassing its checks.

## Failure classification

| Observation | Classification and next action |
| --- | --- |
| Launcher failure before Run; `run_invoked=false` | Setup/registration failure. Preserve stage/HRESULT and any exact task; inspect before choosing a new numbered launch. Never assume no registration from a missing start receipt. |
| Run uncertainty, no return, scheduler still queued/running | Unresolved/live launch. Inspect only; no parallel launch or deletion. A stalled heartbeat is not proof of exit. |
| No return or parent-failure/capture proof after scheduler termination | Interrupted/unproven attempt, including 24-hour termination, logoff or host loss. Process absence does not repair proof; do not manufacture parent-failure or reuse partial results. |
| `BENCHMARK_STOPPED`, `CAMPAIGN_STOP_LATCHED`, or any fixed Stop file | Latched cancellation. Check cleanup, retain request, no resume of this campaign. Malformed Stop (`CAMPAIGN_STOP_*`, JSON/path failure) fails closed too. |
| `CAMPAIGN_RESUME_SOURCE_OR_MACHINE_CHANGED`, source/profile/request/XML/hash mismatch | Binding failure. Preserve evidence and investigate source/environment drift; never weaken or rewrite bindings. |
| `CAMPAIGN_PRIOR_OWNER_HELD`, `BENCHMARK_CLEANUP_HELD`, handle-close uncertainty, tainted Job, missing exit | Ownership/proof failure. Stop the resume path until the exact owner is reconciled; no name/PID-only killing or invented zero. |
| Native stderr/log error, phase/wall limit, early exit, missing counters, growth/status-gap failure | Workload/invariant failure, not an interrupted successful measurement. Preserve phase, logs and cleanup; diagnose before deciding whether a manual new attempt is justified under unchanged source. |
| `CAMPAIGN_ATTEMPTS_EXHAUSTED` | Fixed retry budget exhausted. No fourth attempt, slot deletion or hidden automatic retry. |
| Summary FAIL/GAP or `CAMPAIGN_MEASUREMENTS_NOT_PASS` | Complete or partial measurement does not meet the profile. Preserve it; do not relax thresholds or relabel as PASS. |
| All raw checks and summary PASS, scheduler terminal0 | Candidate evidence only. Frozen final closure, requirement mapping and two independent critics still precede coordinator GT06 acceptance. |

No completed earlier gate or diagnostic is rerun merely to prepare this
handoff. Earlier source-bound probe/Stop evidence remains in `probe-source-01`
and its original raw roots; it is not evidence that this full campaign finished.
