# S46 scoped public selector implementation evidence

Status: PASS focused implementation regression. NOT independent acceptance; TICK=no.

Owned files: selector_pipe.py, selector_contract.py, test_selector_public.py, SELECTOR_PUBLIC.md. No commits, plan edits, or generic safe_open capability changes.

## Result

- Owned process limit: 90 seconds; actual unittest duration: 20.602 seconds.
- 53 tests / 53 passed / 0 errors / 0 failures / 0 skips.
- Captured target exit 0; host exit 0; wrapper exit 0; no timeout; owned process tree verified clean.
- Snapshot closure: `1908bf377f3686a94790468ba2d43437dc5a83e386e33763feda7aba29461b19`.
- Snapshot unchanged. Assigned source files unchanged during run. Shared tree changed only tests/protocol/test_managed_service.py during this attempt; this is a scoped snapshot test, not a source freeze.
- Schema digest: `sha256:c61de54568e69a31559f3050898ef3a36d0d296a31bca7885e1cd6ab6ea77d70`.

## Behavior

Exact ManagedFixtureOwner registration checks live Registry custody, event witness, protected root identities, selector/consumer ownership, and closed/poison state. Discovery authenticates and advertises only the current fixed fixture.active-release resource scope; readonly, pending, held, stopped, or insufficient-scope sessions do not receive activate. Inspect emits 11 fixed safe metadata fields bounded to 4096 bytes. Commands retain the 8192-byte whole payload grammar and existing lease/fencing/CAS checks.

Factory/close share the managed lifecycle lock. Broker close rejects active service ownership. Admission publishes its wake signal before response I/O. Authenticated and shaped Stop/Cancel latch cancellation before waiting for managed storage validation; Stop also latches the selector stop event. Invalid/revoked requests cannot set those signals.

## Coverage and limits

Public tests exercise live native protected files plus Registry custody and actual readback across create and replacement, exact duplicate receipt/no effects, readonly and pending restart, failed delivery wake, metadata no event/custody/blob/file effects, auth/revocation/project/role/version checks, fixed digest, detached binding, safe output filtering, and early Stop while a selector lock is held.

Frame reads/writes in this focused public suite are substituted at AppContainerEndpoint; it does not establish native client boundary or managed service lifecycle acceptance. Existing selector, file-consumer, and managed-owner regressions are included. Full exact-closure integration and independent acceptance remain coordinator work.

Attempt-01 is retained: 51 tests, 11 errors caused by the older fixture_frame helper refusing /v1/inspect. Attempt-02 uses the same framed protocol encoded locally, adds the Stop/revocation regression, and passes. No failed evidence was overwritten.

## Assigned file hashes

- `host/core/selector_pipe.py`: `03c33f0804a5bfe78548c70803b57ebd059c3e4350fee03cbcec2a471f16451d`
- `host/core/selector_contract.py`: `4ee06edc621059fe9499fbb044c181323f59a01ed55e1d7f322e90ed17973b2c`
- `tests/protocol/test_selector_public.py`: `0bc50b1640846320f3d0edd07f14fb99d1d5d3815a7ebe9b1f5ddb576f26024e`
- `host/core/SELECTOR_PUBLIC.md`: `ef8ea48a165b94e21b55e6e435d3d529af4ed4a51a7199e13c2a9555cb39ffbf`

## Reproduction

`python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s46-public/run_focused.py --attempt attempt-03`

Existing attempt directories are immutable; use the next unique attempt identifier. See attempt-02/capture.json and source-closure.json for exact inputs, command ID, timestamps, artifact hashes, actual host record, and test IDs.
