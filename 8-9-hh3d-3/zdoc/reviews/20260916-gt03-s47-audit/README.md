# GT-03 S47 trusted-editor checkpoint

AUTHORITY=0. IMPLEMENTATION CHECKPOINT ONLY. GT-03 remains IN_PROGRESS.

Final package: `../20260916-gt03-s47-editor-08/`.
Source closure: `ea1ec66db84efe3c2708c48337eb5ff56f799cd946a71eebccfee13940668593`.
Python 51/51; actual editor 97 edit, 7 reopen, 28 contract checks. All three
engine children and wrappers exited0 with verified empty owned process trees.
Logs are clean. Source snapshot, executed project code and pinned binary are
unchanged. Full semantic state revision is identical after a separate reopen.

| Requirement | Evidence | Limit |
| --- | --- | --- |
| Main-thread scene/resource changes | edit result: create/update/remove, native BoxMesh and owner readback | Internal projection, no public service |
| Undo/redo and stable generation | edit result: exact undo/redo revision, actual scene reload | In-memory receipts only |
| Manual edits preserved before effects | same-state parent replacement; external/shared mesh; detached group, persistent signal, queued deletion | Finite local/unshared BoxMesh fixture |
| Scene serialization/reopen | packed scene; separate engine reopen; exact full-state revision | Fixture ResourceSaver, not transactional publish |
| Shared Request interoperability | actual native snapshot -> Python validator -> JSON -> Godot preview + create apply;14 host rejections | Generated remove/history deferred in this lane; separate native edit tests cover their execution |
| Complete project revision bytes |19 bundle tests bind exact scene+script bytes and reject stale script base | Inert codec; observations are not attestations |
| Evidence refusal |17 tamper tests and result/progress checks | Process provenance independently checked by owned runner |
| Untrusted process boundary | separate AppContainer startup report, zero capabilities, denied private access | No full disk bound;2 attributed volume-query errors; no arbitrary-script acceptance |

GT-02 remains accepted at `0c3b00a` on its exact S46 closure. Its core/protocol
sources were not changed; `s46-audit/verify_acceptance.py` still verifies both
independent PASS records. These S47 workers authored implementation and their
cross-review is not two independent GT-03 acceptance votes.

Preserved failures: editor01/02 rejected native default object properties;
03 added precise native inventory.04 passed semantic checks but correctly
failed for duplicate scene UID caused by the diagnostic copy.05/06 failed
with actual native exit0xC0000374: the fixture freed a retained parent after
history custody already freed it.06 flushed progress narrowed failure to that
cleanup.07 then passed97/7/28 +34 Python;08 adds17 evidence tamper tests and
executed project/binary byte checks. None of those old results is relabeled.

Generated Godot editor caches from01–04 stay on disk and are excluded by the
reviews `.gitignore`; cleanup was policy-blocked. They are not source/evidence
inputs and are excluded from the artifact manifest. All logs, results, host
records and frozen source copies remain.

Reproduce from `studio` with a fresh output name:
`python -B tests/godot/run_editor_probe.py --run-id NEW_UNIQUE_ID --output ../zdoc/reviews/NEW_UNIQUE_DIRECTORY`.
Audit from repository root:
`python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt03-s47-audit/verify_evidence.py`.
The audit rejects changed working source; later implementation must mint a new
checkpoint rather than attach this result to new code.

Remaining: authenticated host/effect-time authority; Godot-specific journaled
scene+script save and crash/readback recovery; a disk-bounded parser/editor
sandbox; attached-script preservation; editor/Play role handoff; then two fresh
independent critics on one complete GT-03 closure. Full GT03 coverage review
is `../20260916-gt03-s47-coverage.md` (binds earlier07, not08).
