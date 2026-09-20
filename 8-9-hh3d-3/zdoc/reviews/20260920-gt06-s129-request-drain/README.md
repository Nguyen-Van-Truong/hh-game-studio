# S129 request-thread drain repair

`AUTHORITY=0`; GT-06 remains unaccepted. No engine, benchmark campaign, formal
retry, dataset contribution, gate adjustment, plan edit or commit occurred in
this repair. The changes are confined to `studio/host/core/transport.py`, new
`studio/tests/protocol/test_transport_request_drain.py`, and this evidence folder.
Baseline Git HEAD was `30d5f7001c1767cd6e4c49d6d82bc3f1abee40d6`.

The independent host-only evidence at
`../20260920-gt06-s129-host-quiescence/run-02/result.json` identified a concrete
cleanup defect: an incomplete, unauthenticated HTTP request outlived
`LoopbackFixtureHost.close()`. That result does not establish the S127 host
counter failure's cause. Its three normal groups reported stable handles;
this repair makes no leak, no-leak or root-cause claim.

## Before and after

The new real-socket test starts incomplete headers on both listeners, waits
until both request handlers are entered, calls host close, and checks the
captured server sockets and request threads before closing either client.

Before: the test failed with both request threads still alive after close.
`before-test.json` records actual child exit `1`, the command and source/test
hashes. `transport.before.py.txt` and `test.before.py.txt` preserve the exact
prepatch source and test; `before.stderr.txt` and `before.stdout.txt` retain
unaltered child output.

After: all **61 focused transport tests passed**, actual child exit `0`, in
`focused-tests.json`; unaltered output is in `focused.stderr.txt` and
`focused.stdout.txt`. This includes all eight new request-drain tests.

## Lifecycle change

Each listener keeps a locked `weakref.WeakSet` of standard `threading.Thread`
objects, registered before start. A failed start removes its registration and
releases the reserved connection slot. Completed threads receive no persistent
strong reference from the listener, preserving normal thread/resource disposal.
The existing `ThreadingMixIn.process_request_thread` still owns request handling
and socket shutdown; the connection semaphore still releases in `finally`.

Host close stops both accept loops before snapshots, closes both listening
sockets, explicitly drains request threads, and joins started fixed threads.
The existing `readback_timeout_ms / 1000 + 2` duration supplies a shared remaining
join budget; no request, wire, benchmark or profile timeout was changed. Cleanup
continues across errors and raises the first error with local `cleanup_owner`
and secondary cleanup errors, so a caller can retry cleanup of the same host.
The request registry retains live threads weakly while Python's active-thread
ownership keeps them reachable. A separate `drain_requests` method avoids
overriding constructor-time `server_close` behavior. Unstarted and partially
started hosts can close without waiting on a nonexistent serve loop.

Coverage includes real incomplete headers on both listeners; both accept loops
stopping before either request snapshot; failed request-thread start releasing
its slot and registration; completed threads becoming collectible while the host
is still running; a bounded held-request drain failure that still closes/drains
the other listener and joins fixed threads, followed by successful retry; a
listener-close failure with remaining cleanup; unstarted/partial startup; and
second-listener constructor failure.

## Reproduce

From the repository root, without any concurrent benchmark or engine run:

```powershell
python -B -m unittest discover -s 8-9-hh3d-3/studio/tests/protocol -p 'test_transport*.py' -v
```

The new tests use only owned loopback sockets and temporary fixture journals.
Runtime source, test hashes, actual child exit, timestamps and exact invocation
are in the focused-test receipt. The artifact manifest binds the preserved
source, raw outputs and report. This is candidate runtime evidence; previous
critic signatures are not transferred to the changed source.
