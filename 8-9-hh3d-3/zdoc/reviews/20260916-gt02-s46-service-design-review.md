# S46 managed service design review

Verdict: FAIL for the reviewed pre-fix implementation. TICK=no. This is implementation feedback, not independent acceptance: the reviewer authored the public broker lane.

Reviewed HEAD: `1951d802fd570a435198900bd5ea382c2e00b179` plus S46 working source. Exact diagnostic source closure: `c8bfc4a717d2f07570c5758194e6b7fd2cff522a05f8070538f87523e107191a`.

## P2 — Service deadline permits fresh dispatch while the pump is blocked

Location in reviewed bytes: `studio/host/core/managed_service.py:106-112` (`_serve`) and `:121-140` (`_pump`).

The readers check the overall service deadline before blocking in `serve_one()`. That call reads and dispatches a frame without another service-deadline check. The pump supplies the idle deadline timer, but cannot enforce expiry while inside an admitted synchronous storage phase. Consequently a reader already waiting when the deadline passes can authenticate and dispatch a new mutation using the still-valid session credential, and only ends the service on its next loop iteration.

Concrete owned reproducer: use the real managed storage/Registry fixture and real service threads, substituting endpoint peer/frame I/O as existing lifecycle tests do. Start a 700 ms service, admit activation, gate its already-admitted `selector.stage` call, receive ACCEPTED_PENDING, wait until 50 ms beyond the service deadline, then send a fresh `/v1/lease` on WORK. The server returned a new lease; the durable journal sequence increased from 4 to 5. This is fresh post-deadline admission, separate from the documented allowance for a previously admitted synchronous phase to finish.

Evidence: `20260916-gt02-s46-service-review-evidence/run-01/diagnostic-stdout.txt`, `diagnostic-host.json`, `capture.json`, and `source-closure.json`. Diagnostic test 1/1 in 0.899 seconds; actual target/host/wrapper exit 0, no timeout, owned process tree verified clean. The diagnostic passes only when the defect is reproduced. Snapshot and source were unchanged during this run. The harness and reproducer are retained beside run-01.

Requested fix: enforce the service deadline independently of readers and pump, immediately hold fresh admission, invalidate the entire bound logical session (including rotations), and request endpoint cancellation. Keep the existing owner/drain rules and permit only already-admitted synchronous work to finish. Add a bounded regression with a blocked pump and a reader waiting across expiry. The coordinator acknowledged the finding and is implementing a separate finite deadline watcher; that fix was not present in this reviewed snapshot and has not been verified by this report.

## Other paths examined

No additional concrete defect established in these reviewed paths:

- Managed owner/factory/service association uses the same owner lifecycle lock; owner and broker refuse closure while service owns them.
- Failed drain or endpoint cleanup retains owner, broker, endpoint and live-thread references, with retryable cleanup ownership.
- Startup failure after partial thread creation retains already-started threads for explicit join/close.
- Admission publishes the wake event with the job before response I/O; clear-before-state inspection and identity-checked job clearing avoid the inspected lost-wake and replacement-job races.
- Work failure holds new phases while keeping control alive. Control failure removes the bound session ID, including rotated credentials.
- Public Stop/Cancel authentication, project, shape, identifier and scope checks precede control signals; Stop now signals before waiting on managed storage registration.

The transferred endpoints remain trusted local objects: callers must stop using/closing them after successful transfer. This review does not claim protection against a trusted caller violating that ownership contract. OS Job enforcement remains a launcher responsibility and is not established by lifecycle frame mocks.

## Scope and hashes

Read-only review of managed_service.py, managed_fixture.py lifecycle close guards, and test_managed_service.py, plus the broker/endpoint/session dependencies needed to assess interactions. No source, test, plan, or production documentation was edited. Only this report and unique review evidence were written. No commit, frozen-candidate acceptance, or native AppContainer boundary acceptance is claimed.

- `host/core/managed_service.py`: `6d9f2c89aa7b29d8c4b7d49c5cc73d43884fb9efd2e80837282d56632ef5560e`
- `host/core/managed_fixture.py`: `5be6efa0c9daab785cbc1661a5e03a71d6fb14bd30892f15f2fd75ab81191b3b`
- `tests/protocol/test_managed_service.py`: `4c8144a3dad5dd50b470d2808c38cf500c6a639674193f3a58df931929e11192`
- `host/core/selector_pipe.py`: `03c33f0804a5bfe78548c70803b57ebd059c3e4350fee03cbcec2a471f16451d`
