# GT06 S121 boundary repair review

Date: 2026-09-19 (Asia/Saigon)

## Scope

This is an offline review of one uncommitted candidate against the retained
S119 lookup boundary. It is diagnostic evidence only. It does not change the
GT06 acceptance gate and is excluded from F13/F14.

## Candidate

The candidate moved the read-only `/v1/lookup` and `/v1/archive` dispatch path
outside `LoopbackFixtureHost._lock`, then reacquired the host lock only after
the durable journal read. The intent was to avoid making a slow journal read
hold the host lock while a completion worker finishes.

The candidate was never committed and was restored to the pinned source after
verification. No source, profile, workstation, timeout, gate, baseline, RSS
policy, or priority change remains.

## Verification

The focused recovery suite was run against the candidate:

```text
python -B -m unittest 8-9-hh3d-3/studio/tests/protocol/test_transport_recovery.py
```

Result: 3 failures in the socket-cut recovery contract (17 tests total):

* `test_pending_ack_socket_cuts_preserve_lookup_and_one_effect` failed for
  `after_dispatch` and `before_reply`; the eventual lookup was `UNKNOWN`
  instead of `COMMITTED`.
* `test_stop_ack_socket_cuts_preserve_stopped_state_on_reconnect` failed for
  `after_dispatch`; the reconnect lookup was `RECOVERY_REQUIRED` instead of
  `STOPPED`.

The fixture-pipe and verified-journal suites remained green (18 tests):

```text
python -B -m unittest 8-9-hh3d-3/studio/tests/protocol/test_fixture_pipe.py 8-9-hh3d-3/studio/tests/replay/test_verified_journal.py
```

The candidate also passed `py_compile` and `git diff --check`. Those checks do
not override the recovery failures.

## Decision

Reject the candidate and retain the original pinned transport. The failures
show that separating the durable read from the host-state lock changes the
pending/stop reconciliation contract; the S119 lifecycle correlation alone is
not enough to choose a safe repair. The failures are preserved as a negative
repair result so a later design can distinguish journal serialization from
the host-lock boundary without weakening any gate.

Formal GT06 retry remains closed. A future repair requires a new static design
and a fresh bounded diagnostic with a new ID; it must preserve the original
profile, gates, source/workstation pins, and all failed evidence.

AUTHORITY=0
FORMAL_PASS=false
