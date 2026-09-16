# S52 publication owner implementation review

AUTHORITY=0. Read-only implementation review, not a gate critic or acceptance signature. No source edits or engine reruns were performed for this review.

## P1: final durable completion is outside phase admission

`studio/godot-addon/publication_owner.py:274-276` checks authority once, then performs durable READBACK and COMMITTED outside a registered STARTED effect. A Stop/revoke can occur during READBACK, report `draining=false`, and still be followed by COMMITTED and `public_ack=true`. This is distinct from the explicitly documented behavior for an already STARTED phase, where Stop honestly reports draining.

A bounded local scheduling reproduction invoked actual `_save` and actual `PublicationSession` with mocked editor/validator/journal boundaries; journal.readback called the real `sessions.stop(grant)`. Result:

```json
{"stop_at_readback":{"stopped":true,"held":false,"draining":false,"public_ack":false},"reply_status":"COMMITTED","reply_public_ack":true,"commit_calls":1}
```

Minimal fix: register a final `commit` phase and use `_phase` around final current adoption observation plus READBACK and COMMITTED. Before STARTED, Stop/revocation/expiry prevents completion; after STARTED, completion is an accounted draining phase. Preserve UNKNOWN if disk completion cannot be proved. Add regression for Stop before start, during READBACK, revoke during READBACK and incomplete commit. This does not require holding the session mutex over disk or IPC.

## P2: advertised read-only inspection requires write authority

`publication_owner.py:174-181` unconditionally obtains a lease from the grant session and passes it into mutation-style validation for both operations. `lease()` requires `scene.save`, so an inspect-only issued grant can discover but cannot inspect. Discovery after Stop still advertises inspection; once its existing short lease expires it becomes unusable because Stop prevents lease renewal. Define a genuine read-only inspection context/route, or explicitly narrow grants/discovery until this is implemented. Do not grant `scene.save` merely to allow reads.

## P2: probe cleanup exception skips later owners

`studio/tests/godot/run_publication_probe.py:129-132` calls `server.close()`, `owner.close()`, then `reopened.close()` in one finally block. A drain/close exception from an earlier resource skips the later cleanup owners. The outer owned runner can still kill the process tree, but this skips deliberate native-owner draining and masks the original failure. Attempt all cleanup owners with separate try/finally or collect exceptions while retaining references; record actual cleanup failures and keep the run diagnostic.

## Verified ordering and limits

- Request parsing, operation allowlist, registered Godot grant/catalog/project checks precede new admission.
- Exact-digest duplicate lookup happens before current deadline/lease validation and checks the durable receipt before returning COMMITTED. No ordinary writable restart constructor is present.
- Editor `prepare_effect(capture)` performs a registered no-write preparation. CAPTURE_PREPARED is durable before `capture()` sends its single-use consume. The editor checks session, root, generation, revision, input files and deadline again on its main thread immediately before capture.
- `_phase` STARTED is the stated linearization point for capture/stage/select/adopt. Stop/revocation after STARTED may allow that phase to finish and reports draining; Stop before STARTED rejects it. The preparation→consume gap is not independently a false-ACK bug under this explicit contract.
- Validation uses exact capture bytes and full captured semantic bytes. Ready inspection precedes selector activation; later manual edits are rejected again by adoption's main-thread precondition. An edit between ready inspection and selector CAS can still produce SELECTED followed by UNKNOWN/reconciliation rather than an ACK. This scheduling cut needs an adversarial integration test; do not claim it preserves the old selected generation without running that test.
- Public COMMITTED is emitted only after journal.commit returns a durable COMMITTED receipt, and `_reply` rechecks the journal receipt hash. Observation after actual adoption verifies revision plus current generation/root/working files. No obvious direct forged-receipt or reopened-owner ACK path was found in these two files.
- Current native probe covers a successful authenticated save, normal duplicate lookup, foreign bearer and Stop after completion. It does not yet exercise Stop/revoke during effects, manual edits during validation, response loss after commit or restart at each phase.
