# Checked CLI Job ownership

`cli_job.py` owns one unnamed, non-inheritable Windows Job per gated CLI helper.
It does not own Docker containers and does not modify the accepted bootstrap
runner. `create(process)` configures `KILL_ON_JOB_CLOSE` without breakaway and
checks assignment before returning an `Owner`. The caller must not send the
helper's `GO` token until create succeeds.

```python
cli_job.require_no_holds()
owner = cli_job.create(gated_process)
# Only now release the caller-owned GO gate.
count = owner.active_count()  # actual integer, or None on failed query
owner.terminate()             # checked; does not itself claim process exit
owner.close()                 # observes zero active, then checks CloseHandle
record = owner.snapshot()
```

`close()` returns only after a successful zero-active query and successful
native close. If processes remain, it requests owned termination and polls for
at most one second. Unknown/remaining activity prevents native handle close;
the handle and owner remain available. After a successful close, repeated
`close()` calls never call CloseHandle again. The closed owner's zero result
is its recorded pre-close observation, not a new native query.

`JobError` carries `code`, `native_error`, and `cleanup_owner` when a handle
still needs cleanup. Constructor configuration or assignment failures attempt
the same checked cleanup. If that cleanup fails, the exception and `HOLDS`
retain the owner. A failed constructor has not released the helper gate: the
caller must also stop/wait its exact helper process, including the case where
assignment never succeeded. The Job cannot claim an unassigned process exited.

Every native query, terminate and close result is checked. Failures taint that
run even if later cleanup succeeds. `snapshot()` reports `configured`,
`assigned`, `closed`, `handle_retained`, `tainted`, `zero_observed`,
`active_count`, `failed_operations` and `native_error`. A clean caller result
must require closed, zero observed, and no taint, in addition to its separate
process-exit/stream checks. A successful terminate request alone is not proof
that no processes remain. [Microsoft TerminateJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject),
[Microsoft CloseHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle).

The module uses locked owner operations and a locked registry capped at 16 live
owners. Retained failures are a deduplicated subset of that registry, preventing
unbounded handle allocation through this API. `require_no_holds()` and new
`create()` calls reject while any failed owner remains. `retry_cleanup()` makes
one attempt per held owner, with at most one second of settling per owner,
returns their snapshots, and retains every unresolved failure. It never drops
a handle merely to make the registry empty. Recovered owners remain tainted
for their original result while allowing later independent work.

The handle is private to this module; callers must not close or duplicate it.
The caller owns process/pipe handles and evidence. Job creation with null
security attributes yields a non-inheritable handle; successful last-handle
closure with the configured flag terminates the associated processes. This
fail-safe does not replace the module's explicit zero-active evidence or the
Linux container's separate deadline. [Microsoft CreateJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw).

`tests/godot/test_cli_job.py` contains eight injected tests and four actual
Windows tests: clean gated exit, descendant termination, a real native handle
surviving injected close failure, and native constructor handles surviving
configuration/assignment plus cleanup failure. The native tests use bounded
controlled Python helpers and capture actual exits; they start no Docker or
Godot process. No public capability or acceptance flag is enabled here.
