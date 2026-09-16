# S50 publication-state v2 cross-review

AUTHORITY=0. 2026-09-17. Bounded implementation review for the next native journal consumer, not formal GT-03 acceptance.
Scope: `publication_state_v2.py`, its tests and `PUBLICATION_STATE_V2.md`. No source edits, engine/Docker/native storage calls, or full-suite rerun.
One small pure counterexample used the existing test history helpers; actual Python exit was 0. No test methods were executed.

## Finding requiring correction

**READBACK can claim an observation made before ACTIVATING and still reach internal COMMITTED.**
Reviewed source: `publication_state_v2.py` SHA-256 `603b8004e5cdb7ee57c03689f5fcf67759639529b3da3b932d5dcb5827a2a426`.
`_observation` only bounds the observation timestamp between PREPARED and its enclosing event. READBACK also requires distinct observation/session IDs from VALIDATED, but it has no lower bound at activation.

Reproduction with the unmodified `history()`/`next_event()` helpers:

```python
rows = helpers.history()                    # normal scene.save success
rows[5]['observation']['observed_ms'] = rows[1]['observed_ms']
state = publication.replay(rows[:6])
state = publication.reduce_event(state, helpers.next_event(state))
assert publication.lookup(state, 'cmd.one')['phase'] == 'COMMITTED'
```

Observed values: PREPARED/readback observation `101`; VALIDATED observation `103`; ACTIVATING event `104`; terminal result `COMMITTED`, `public_ack=false`.
The terminal event is regenerated so its readback hash correctly binds the backdated READBACK record; this is not an unrelated hash-tamper failure.
Fresh IDs alone cannot establish that a read occurred after the selection effect. This matters when the future journal consumer treats accepted READBACK history as evidence of phase ordering.

Recommended bounded correction: retain the ACTIVATING event time in the command, require READBACK observation time to be at least that boundary, and add a focused regression for the pre-activation observation above.
Equal millisecond timestamps may remain valid; actual ordering/attribution must still come from the native owner. Preserve the existing rule allowing terminal persistence after the original deadline without admitting a new effect.
The coordinator and reducer owner were notified. This report binds the failing reviewed hash above, not any subsequent fix; correction needs a separately recorded source hash and targeted test result.

## Checks that held in this review

- The complete eleven-file metadata algorithm, fixed roles/caps, trusted-source revision and project revision match codec v2. STAGED recomputes canonical manifest bytes and checks its native hash/length.
- Descriptor root matches CONFIG; every file is on that volume, differs from the root FileID, and the twelve candidate FileIDs are unique. Exact planned names bind all eleven contents plus `@manifest`; names cannot recur in retained commands.
- Script replacement preserves all ten non-script files and matches admitted script hash/length. A separate fresh candidate semantic observation binds the full project digest and pins; exact reuse of that fact for VALIDATED is explicitly checked.
- Scene save preserves every non-scene file while binding the admitted live semantic revision, allowing unsaved scene edits to differ from the currently published scene state.
- Exact event/nested shapes, typed integers/booleans, phase order, monotonic event time, original authority/deadline recheck at ACTIVATING and readback-event hash binding reject inconsistent declared histories.
- PREPARED reserves five remaining success events plus STOP within the 256-event bound. Command/name/observation retention is bounded; native byte/file/event capacity still belongs to the real owner.
- STOP before activation retains last-good and terminates only the declared publication; staged bytes may remain. After possible activation it holds UNKNOWN. Existing UNKNOWN cannot advance, and replay/lookup never authorize execution.
- Terminal lookup retains the original digest/receipt. Conflicting IDs and duplicate PREPARED events reject without changing the previous immutable state. Public ACK and engine-effect flags stay false.

## Native-consumer prerequisites, not reducer proof

CONFIG accepts a self-consistent initial metadata/selection attestation without an initial descriptor, native readback or durable baseline transaction. A new journal must not infer actual selected-state readiness from CONFIG alone.
The journal owner must establish the baseline from the trusted factory and actual protected descriptor/manifest/selection readback before accepting publication effects. Keep historical v1 separate; do not synthesize its missing v2 source files.
The reducer is not a lease issuer: highest fence and same-fence lease/expiry consistency come from PREPARED observations. Session authentication, revocation, current lease checks and the immediate pre-effect fence remain native coordinator responsibilities.
Pure FAILED/STOP does not clear a held ProtectedBundleStore, reclaim files or permit retry after an uncertain native write. The owner must preserve native cleanup ownership even if the consistency history has an early terminal result.
Current terminal receipts retain descriptor hashes, while the canonical event history retains the full descriptor. A future consumer must resolve and verify that history rather than manufacture file identities from terminal metadata.
No new issue was found in metadata hashing, name/root binding or Stop/capacity handling during this bounded pass. This does not replace the full frozen native/engine evidence or independent acceptance reviews.

## Exact reviewed files

Paths relative to `8-9-hh3d-3/studio`:

| Path | SHA-256 |
| --- | --- |
| `godot-addon/publication_state_v2.py` | `603b8004e5cdb7ee57c03689f5fcf67759639529b3da3b932d5dcb5827a2a426` |
| `godot-addon/PUBLICATION_STATE_V2.md` | `d37ea405b80ebf77b793c3f3069901cd8f60361ebb0b9d1c4ba42d8b57e86022` |
| `tests/godot/test_publication_state_v2.py` | `a978c5d16f8f0eae86d72920e3506a843096b32b928ca2d19f216440f504dc1f` |

No formal PASS/TICK verdict is issued. This review's actionable finding is the missing post-activation observation-time bound.
