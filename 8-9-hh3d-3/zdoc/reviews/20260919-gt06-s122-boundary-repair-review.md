# GT06 S122 lookup boundary repair review

Date: 2026-09-19 (Asia/Saigon)

## Evidence boundary

S119 showed the stock lookup request could remain outside the lookup handler
while `host.finish` held the host lock through journal work. The retained
source also acquired that same host lock in the local disconnect probe before
dispatch. This review tests a narrow source change against that exact
boundary. It is diagnostic evidence only and is excluded from F13/F14.

## Repair candidate

The candidate makes three coupled changes in
`studio/host/core/transport.py`:

1. Local disconnect fault state uses its own mutex, so an unarmed or matching
   test seam cannot serialize a real lookup behind host state or journal I/O.
2. Read-only lookup dispatch validates the session and route before entering
   the host lock. A host-owned immutable-by-convention pending snapshot serves
   a live admission without a durable read; the snapshot carries the journal
   retry expiry and is removed only after a terminal journal write (or an
   explicit recovery failure). Expired entries fall back to the journal.
3. Duplicate admission checks use the durable lookup path, preserving retry
   horizon and archive semantics; this fast path is therefore not an implicit
   retry or a new authority.

The original profile, source scope, workstation, timeouts, gates, baseline,
priority and RSS policy are unchanged. The candidate is not a game feature and
does not change Godot/Blender behaviour.

## Verification

Sequential focused suites passed:

```text
python -B -m unittest \
  8-9-hh3d-3/studio/tests/protocol/test_transport_recovery.py \
  8-9-hh3d-3/studio/tests/protocol/test_transport.py \
  8-9-hh3d-3/studio/tests/protocol/test_transport_fault_lock.py \
  8-9-hh3d-3/studio/tests/protocol/test_transport_observation.py \
  8-9-hh3d-3/studio/tests/protocol/test_fixture_pipe.py \
  8-9-hh3d-3/studio/tests/replay/test_verified_journal.py \
  8-9-hh3d-3/studio/tests/replay/test_transport.py
```

Result: 80 tests passed. A bounded local stress probe held terminal journal
write for 2.2 seconds; lookup returned `ACCEPTED_PENDING/QUEUED` in 0.015 s.
An expiry probe confirmed that a pending entry past its retry horizon falls
back to `RETRY_HORIZON_EXPIRED`, rather than remaining queued. `py_compile`
and `git diff --check` also pass.

## Decision and next gate

This candidate is suitable for a fresh source checkpoint, but it is not a
formal GT06 result. Commit the verified source closure, then run one fresh,
bounded diagnostic with the original workload/gates to distinguish the command
lane. Keep S119/S116 failures immutable and excluded. A formal GT06 campaign
still requires 10 fresh host/editor pairs × 35 batches and all dataset,
hash, exit, tree, Job and handle evidence before the final manifest and two
new independent critics.

AUTHORITY=0
FORMAL_PASS=false
