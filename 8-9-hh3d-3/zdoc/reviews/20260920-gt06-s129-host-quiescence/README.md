# S129 host request-lifetime diagnostic

AUTHORITY=0. Host-only diagnostic; no engine, formal campaign, dataset, acceptance verdict, gate change, runtime edit, or commit. This packet answers whether an owned HTTP request can remain alive after the existing host `close()` returns. It does not explain S127's batch18 host counter change 209→210. S127 ran 100 native cycles between HTTP and joint observation, so these short samples cannot establish a missing 50 ms drain as that cause.

## Result

The clean `run-02` child exited naturally with code 0; its supervisor captured and reaped that actual process. Supervisor duration was 3.009 seconds, child diagnostic duration 2.355 seconds. Three `CommandProducer.run_diagnostic()` groups each exercised the real loopback HTTP 5 inspect / 3 rejected / 2 admitted mix, plus the producer's auxiliary discovery, lease, lookup and Cancel calls. All six admitted fixture effects read back; every Cancel reported no effect. The underlying effect is the existing in-process mock fixture, with no native engine effects.

Actual counts below come from `GetProcessHandleCount` prebound before baseline, using the current-process pseudo-handle. The producer's existing test `SyntheticObserver` separately reports fixed RSS 1,000,000 and handles 10; those numbers are synthetic and are never substituted for the actual counts.

| Boundary | Actual handles | Active requests | Live request threads | Live fixed host threads |
|---|---:|---:|---:|---:|
| Before host | 143 | 0 | 0 | — |
| Normal host started | 172 | 0 | 0 | 3 |
| Each of three groups: immediate | 175 | 0 | 0 | 3 |
| Each group: active-zero, 50 ms, 200 ms | 175 | 0 | 0 | 3 |
| Normal `close()` returned | 163 | 0 | 0 | 0 |
| Separate partial-request host started | 192 | 0 | 0 | 3 |
| Partial request accepted, before close | 196 | 1 | 0 | 3 |
| Partial host `close()` returned, client open | 186 | 1 | 1 | 0 |
| Client socket explicitly closed | 185 | 1 | 1 | 0 |
| Request fully returned; 200 ms later | 180 | 0 | 0 | 0 |

The partial request is an intentionally incomplete HTTP header, with no authentication, body or raw request logged. The active-before-close sample caught the thread startup interval: the request had been registered, while the request thread had not entered its wrapper. The host's `close()` returned in 53.223 ms with this request still active and its server socket still owned. Only after the diagnostic closed its client socket did request sequence 229 return from the original `process_request_thread`, with `fd_after=-1`. Original socket shutdown and slot release therefore preceded that final event. All 229 accepted request lifecycles have matching start, thread entry and return records.

Normal-group samples did not reproduce a handle change between immediate, active-zero and bounded settle observations. The counts do not identify kernel object types. The diagnostic retains producer/journal/session and recorder objects until process exit; final count 180 versus initial 143 is not a leak verdict or a target for a proposed threshold. No leak, no-leak, S127 root-cause or benchmark acceptance claim is made.

## Preserved instrumentation correction

`run-01` also exited naturally (code 0, supervisor 3.640 seconds), but its recorder retained strong references to every request Thread to join them later. That changed Windows handle lifetimes: later sampling and `is_alive()` checks released some thread bookkeeping, while other per-thread objects remained retained. Its growing handle totals are contaminated instrumentation evidence and must not be used to characterize the host. The exact first executing script is preserved as `run-01/host_quiescence.execution.py`, matching its source manifest and supervisor hash. Its partial-close lifetime ordering remains visible, but `run-02` supplies the corrected reproduction.

`run-02` records only numeric sequence/fd/thread identifiers, booleans and counters. It does not retain socket or Thread objects in the registry or logs. Cleanup joins any still-live request threads found in this otherwise single-threaded child, after samples; here all 229 had already terminated, so the number requiring an additional join was zero. The six fixed host threads were joined by their two host closes. No extra live thread or owned client socket remained, and the child exited normally. No background helper or engine was launched.

## Narrow repair justified for review

A shutdown lifecycle repair is justified independently of S127: the current `_Listener` uses `daemon_threads=True` and `block_on_close=False`, and host close joins only its three fixed threads. A successful close can thus precede a live accepted request's socket shutdown/slot release.

The smallest candidate is a per-listener weak registry of owned request Threads, protected during registration and snapshot. Register before `Thread.start()` to cover the observed startup interval. Keep the existing slot acquisition, request body timeout, wire behavior and slot release ordering. Remove a failed-start entry and release its acquired slot exactly once. After both accept loops have finished `shutdown()`, close listener sockets, take strong references only to the currently live weak entries, and join within a bounded shutdown budget. A timeout must report cleanup still held, preserve ownership for retry, and must not skip closing the other listener or joining the fixed host threads. Constructor/unstarted close must remain safe. Direct `server_close()` during an active accept loop would need an explicit quiescence guarantee; it cannot assume `shutdown()` already completed.

Weak tracking avoids the first diagnostic's strong retention of completed threads; Python's live-thread registry keeps active thread objects reachable while running. Tests should exercise incomplete request close, registration-before-start, failed start/slot release, constructor close, repeated close, and a forced drain timeout. This recommendation changes shutdown ownership only. It adds no wait to benchmark sampling, no new request timeout, and no counter or equality exemption. Runtime implementation belongs to the coordinator and is outside this packet's write scope.

## Evidence and reproduction

- `run-02/result.json`: numeric lifetimes, samples, compact fixture outcomes and explicit synthetic/actual observation labels.
- `run-02/supervisor.json`: child PID 22104, actual exit 0, natural wait/reap receipt, command, timestamps and stream/script hashes. `stderr.txt` is empty.
- `run-{01,02}/source-{before,after}.json`: identical pre/post hashes for 17 files, including imported project Python sources, the diagnostic and Python's `socketserver.py`. This is the diagnostic import set, not a full GT-06 closure.
- `source-snapshot.json` / `source-snapshot/`: exact imported-source bytes, so later coordinator repairs do not change this packet's offline audit.
- `audit_evidence.py` / `audit.json`: offline checks of every lifecycle, active count, closed fd, exact source/stream hashes, fixture mix, synthetic labels, PID and actual subprocess exit binding.
- `manifest.json`: packet file hashes, excluding the manifest itself.

Initial inspection found HEAD `d81d58a3c7b8390b108abcf0da6c7d13188b3194`, a preexisting modified tools plan and preexisting review artifacts. The coordinator advanced HEAD to `30d5f7001c1767cd6e4c49d6d82bc3f1abee40d6` before these runs; both supervisors record that HEAD and both diagnostic import sets remained unchanged during execution. The only initially observed Python process was the preexisting completion-sound helper; no Godot/HH3D engine was observed. This worker wrote only this new review folder.

From the repository root, with a fresh output directory:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260920-gt06-s129-host-quiescence/host_quiescence.py --out 8-9-hh3d-3/zdoc/reviews/20260920-gt06-s129-host-quiescence/run-new
python -B 8-9-hh3d-3/zdoc/reviews/20260920-gt06-s129-host-quiescence/audit_evidence.py
```

The launcher enforces a 45-second child deadline, records forced termination distinctly if needed, and captures the real wait result. Existing attempts are never overwritten. The short 50/200 ms observations exist only in this diagnostic script.
