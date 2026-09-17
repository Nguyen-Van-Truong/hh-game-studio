# Owner lifecycle draft — no execution or acceptance

Base: `c5e56c7e05e5bf784d1e67741cd44cd18b6bd493`. Exact input-byte hashes and
draft hashes are in `base-manifest.json`. The implementation changes are
limited to the two owner-review findings. No live source was edited, imported,
compiled, or tested by this reviewer; no engine or campaign was launched.

## Proposed changes

- `benchmark_job.py.draft`: preserve the initiating constructor exception,
  its original explicit cause, and `cleanup_owner=self` after either successful
  or failed cleanup. A cleanup failure is retained separately as `cleanup_error`.
  This allows the existing parent handler to record actual closed/zero state
  instead of making an already-clean attempt permanently non-resumable.
- Release the Windows wrapper-process handle explicitly after observed process
  exit, stream drain, and checked Job cleanup. Use the checked native BOOL;
  never use `Popen._handle.Close()` for this proof. Retain the exact Handle object.
  A checked FALSE restores its close flag and allows the retained owner to retry.
  An uncertain result retains the owner, suppresses Handle destructor close,
  and forbids further process-handle operations. A successful close followed by
  failed evidence writing can retry evidence without a second native close.
- Cleanup and successful captures carry `wrapper_process_handle` with required,
  closed, uncertainty, and retained-handle booleans. The capture verifier requires
  the exact successful state, including actual bool types. The campaign derives
  its held-handle count from the Job/wrapper/probes rather than a literal zero.
- `test_benchmark_job_owner.py.draft`: eight inert test methods covering successful
  checked cleanup, FALSE/retry, cancellation uncertainty, evidence-write failure,
  handle identity replacement, both constructor-cleanup outcomes, and capture
  verification with rehashed missing/false/uncertain/type-confused handle proof.
- `test_benchmark_job.py.draft`: give existing fake processes explicit inert
  `_handle`, returncode, and wait state. The owner does not silently skip a
  missing process handle. Neither of those existing tests reaches native close.

The local CPython source inspected was
`C:/Users/truon/AppData/Local/Programs/Python/Python311/Lib/subprocess.py`:
`Handle.Close` at lines 218–221 sets `closed=True` before native CloseHandle;
`Handle.__del__` aliases Close at line 234; Windows `_wait` at line 1580 reads
the exit code and does not close the handle. The draft therefore tracks checked
release separately from the CPython destructor-suppression flag. No proof uses
that flag alone to claim successful native release.

## Integration and verification for the coordinator

`owner-lifecycle.patch` contains both source changes, the existing-test update,
and the new dedicated test. The full drafts are also available for comparison.
Integrate only after the current engine/integration lane has exited and its
cleanup evidence is retained. Check base-file hashes before applying; do not
overwrite any intervening live-source changes.

This is a strict extension of the existing capture format: new verification
explicitly rejects legacy captures missing `wrapper_process_handle`. There is
no migration, backfill, or transfer of acceptance from old evidence. A new
source freeze/campaign is required. If schema identifiers require incompatible
version increments in the final review contract, increment the owner capture
identifier consistently rather than supplying defaults for old records.

After integration, run the new owner tests and existing owner/campaign tests
in the coordinator's serialized verification lane. Then exercise bounded native
owner success and Stop/failure cleanup with fresh evidence, including actual
wrapper and target exits and closed/zero records. None of those checks has been
run for this draft. The patch makes no change to workload, deadlines, limits,
benchmark thresholds, GT progress, or acceptance requirements.

## External campaign Stop — proposal only

Add an explicit, campaign-scoped local control channel handled by the retained
parent owner. Do not infer ownership from a process name, enumerate-and-kill,
or introduce a remote execution endpoint.

1. At campaign initialization, publish a control descriptor with campaign ID,
   campaign-manifest SHA, and unique invocation ID. Keep it outside each measured
   run's source/artifact closure in a fixed campaign control directory. Requests
   are only accepted under that directory, with its local access controls.
2. A small fixed-purpose Stop helper accepts the campaign ID and no PID, command,
   arbitrary file path, or executable. It reads the descriptor, validates path
   containment/reparse/hardlink rules, and atomically publishes a bounded JSON
   request containing schema/version, request ID, campaign SHA, invocation ID,
   and `action=stop`. Use exclusive temp creation and no-overwrite rename.
   This is a local trusted-user channel; an invocation ID is a freshness binding,
   not a substitute for access control or authentication on a network endpoint.
3. The parent polls this fixed request before launching a run, during its existing
   owner polling loop, between runs, and before publishing final completion. A
   valid request is durably latched. If a run is active, call the existing retained
   owner's `tick(stop=True)` and close that exact Job tree through the normal
   failure/cleanup path. Never fabricate child exit or natural completion when
   Stop terminates the helper before it can write its process-exit record.
4. Publish Stop receipt/terminal records bound to the same request and invocation.
   They distinguish request observed, owned cleanup completed, and cleanup held;
   include the actual known exit/Job/handle facts. Stop must remain a failed or
   canceled partial run, even if the process happens to exit zero concurrently.
5. Resumption checks the durable Stop latch first. Reconnecting or rerunning the
   same campaign command cannot resume silently. An explicit new invocation
   bound to a new authorization/request may reuse only complete, strictly
   reverified runs; partial batches never enter the dataset. Default to a fresh
   campaign when actual prior ownership/exit evidence is unavailable.

The channel is not implemented in this patch. Parent polling presently includes
filesystem scans; measure the observed Stop latency before claiming a responsiveness
bound. A checked request cannot retroactively recover missing exit evidence from
campaigns interrupted outside their owners.
