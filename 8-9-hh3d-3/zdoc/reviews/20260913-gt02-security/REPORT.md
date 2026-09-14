# GT-02 security vectors

Status: **CANDIDATE (test-only evidence)**  
Scope: `studio/protocol/core.py` and `studio/host/core/limits.py`; no transport,
editor, or project mutation was performed.

## Verification

Command:

```text
python -m unittest studio.tests.protocol.test_security_vectors -v
```

Result: **8 passed, 1 explicit skip**, exit 0.

The vectors cover prompt-injection text treated as inert data, nested sensitive
key rejection, static no-exec primitive checks, duplicate/malformed/non-UTF-8
wire data, malformed response fields, `UNKNOWN` and `CANCELED` terminal states,
oversize/depth/non-finite values, Windows device/ADS/traversal/reparse path
spellings, and write-path safe-open gating.

## Explicit gap

The only skipped vector is `test_stop_api_is_explicitly_unsupported_when_absent`:
GT-02 currently exposes no transport `Stop`, `Cancel`, or `Abort` API.  The test
does not invent a PASS result.  A future transport milestone must add a real
cancellation command and an integration vector proving deadline cancellation,
owned-process-tree cleanup, ACK/UNKNOWN semantics, and retry idempotency.  The
current `Response(Status.UNKNOWN|CANCELED)` checks only validate wire modeling;
they are not runtime cancellation evidence.

The suite also intentionally does not claim secret *value* redaction in logs:
the current boundary fails closed on sensitive field names, while a dedicated
redactor/receipt policy is still needed before untrusted adapter output can be
published.

