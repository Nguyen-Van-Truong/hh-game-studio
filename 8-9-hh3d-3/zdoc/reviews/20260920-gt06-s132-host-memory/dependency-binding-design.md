# S132 — current replay dependency binding design

Date: 2026-09-20. Status: preparatory static design, AUTHORITY=0. No implementation,
test, engine run, source hash sweep, process control, acceptance or critic verdict.
Only this document was written. The S132 host diagnostic remains coordinator-owned.

The plan read for this review is S132, CURRENT_VALID_WP=GT-06. Its reported current
benchmark/runtime closure is `763191109cd7c7f63de499680291c6b99d77a501dad869078e6d77384ecb20b4`
at runtime checkpoint `b8687415`. Those are plan references, not independently
recomputed hashes in this review. That 53-file benchmark closure is not the complete
replay/service/managed-repair closure.

## Recommendation

Keep the accepted GT05 artifact anchor immutable and introduce one separately frozen
current execution binding for the fixed GT06 fixture. Make the replay source guard
compare against that binding, then remint the affected functional lanes. Preserve
every historical map, raw record and acceptance signature under its original source.

Do not rebuild unchanged art merely to change the runtime source pin. An accepted
GLB can remain an accepted input artifact when the program consuming it changes.
The new claim is that the current runtime correctly consumes those exact accepted
bytes. It is not that the old GT05 producer, validator or publication runs happened
under the current Job/transport implementation.

This needs a small, fixed internal binding reader shared by the existing entrypoints,
one versioned binding artifact, and focused regression/evidence. It does not need a
new generic audit framework, a permissive `allow_stale` flag or a GT05 verifier rewrite.

## Findings from the existing code

| Code | Relevant behavior and consequence |
| --- | --- |
| `studio/host/replay/native_runner.py:69–101` | `accepted_inputs()` pins the original GT05 manifest to `fd0b4a984c7bee261c083c07d461baf55325e936d66df2eeab897b422ee0a02b` and checks each of `consumer.INPUTS` against its raw-file hashes. `sources()` then compares every historical GT05 source-map entry with today's tree, raising `REPLAY_REUSE_SOURCE_CHANGED`. Asset provenance and current execution are already separate operations, but the second uses the wrong generation for legitimately changed runtime code. |
| `native_runner.py:run`, `backend.py:PreparedPlay.prepare`, `repair.py:main` | All enter through `accepted_inputs()` and `sources()`. Updating only the direct native command leaves authenticated Play and managed repair blocked or inconsistently bound. Backend adds all replay Python modules; repair additionally dynamically loads the GT03 publication stack and `build/bootstrap/run_fixture.py`. |
| `pipeline/native_job.py`, `host/blender/ui_host.py` | Replay transitively uses the shared native Job runner, dynamically loaded `godot-addon/cli_job.py`, private-store/safe-create dependencies, the embedded helper and export limits. Job/native Python probes prove their own lanes, not replay menu/input or managed repair. |
| `pipeline/verify_run.py:HOST`, `_Verifier.source`, `verify_chain` | The mandatory host set includes `cli_job.py`. Producer, validator/admission and consumer stage maps therefore depend on it. Current-source mode rejects stale maps and source-version conflicts. Historical mode is explicitly diagnostic and cannot yield `publishable`. Comparator bytes have additional current/installed checks. |
| `pipeline/snapshot_provider.py` | The publication provider calls `verify_chain(require_current_source=True)` itself and requires complete, current, publishable proof contained in its frozen map. A replay binding must not authorize this provider or replace those checks. |
| `repair_replay.py:verified_repair`, `repair.py:verified_fault` | These verify historical frozen source bytes and causal artifacts; that alone does not establish current-source execution. The final evidence join must distinguish historical causal provenance from a new current fault/repair/replay chain. |
| S75 `next/affected-dependency-bridge.json` and `prepare_bridge.py` | Existing precedent records original-map hashes, current projections, exact differences and scoped evidence reuse. It explicitly does not prove dependency-map completeness or raw execution. Extend that pattern with a new record; do not edit the old bridge or treat it as acceptance. |

The accepted GT05 manifest has 143 source files according to its S64 acceptance
record. The exact present delta and missing current dependencies still need a
coordinator-owned bounded comparison after live measurement. This review did not
compute or assert a complete delta list.

## Minimal binding contract

Use two named objects with different meanings:

1. **Accepted input provenance.** Original GT05 acceptance/manifest references and
   exact hashes of the three consumed inputs: `fixture.glb`, `manifest.json`,
   `producer-report.json`. Keep the current hardcoded manifest hash and immutable
   raw-file checks. Join the accepted producer/validation/import records to these
   bytes for the vertical-slice claim; a manifest filename alone is insufficient.
2. **Current execution binding.** A new fixed internal, versioned document containing
   the candidate identity, accepted-input anchor, complete source path/hash map,
   explicit hash domain, toolchain/profile/data pins, and entrypoint/lane identifiers.
   Retain exact frozen source copies and named Git byte proof separately. Run evidence
   records this binding's exact-file hash as well as its source-map closure.

The first implementation should retain the old 143-path set as a conservative
mandatory superset and add the full current closure for replay, service, repair and
their native/child entrypoints. Refresh expected current hashes only in the new
binding. Do not delete inherited paths to get past the guard. This avoids making
dependency pruning a prerequisite for this repair; a later justified narrowing is a
separate change. Per-lane execution dependencies can still be recorded for evidence
classification, with a reason for every excluded broad review/test-only dependency.

A candidate binding is a freeze for diagnostic execution, not an acceptance receipt.
It must not contain inherited critic signatures or `GT05_ACCEPTED_CURRENT_SOURCE`.
The coordinator's installed release selects its fixed path/hash; no remote request
supplies arbitrary maps, paths, override hashes or a success flag. Avoid a
self-referential hash: retain the source-map digest inside the binding and the
binding-file digest in its external release/run record.

All three entrypoints consume the same binding implementation. Preserve the
`REPLAY_REUSE_SOURCE_CHANGED` fail-closed behavior for a mismatch with the selected
current binding. Keep the old GT05 manifest hash check and all payload checks. There
must be no catch-and-continue, runtime rehash-to-accept, fallback to whatever exists,
or caller-supplied old/current exception list.

## Concrete refresh algorithm

1. After the diagnostic is terminal and its evidence preserved, fix a candidate
   source generation. Read the old accepted anchor and existing per-lane maps
   without changing them. Produce new maps/projections under fresh IDs. Record
   every added, removed and changed path; unknown/missing paths block reuse.
2. Build the conservative execution closure from the inherited set plus explicit
   entrypoint dependency manifests. Include statically imported modules, dynamic
   loaders, helper strings via their containing files, child drivers, Godot resources,
   schemas, fixture/source pins, profiles, lockfiles and generated project inputs.
   Include `native_runner`, backend/service paths and the managed-repair publication
   stack. A single interpreter's `sys.modules` is supporting coverage, never the
   sole inventory; entrypoint and child differences must be represented.
3. Classify each old evidence claim using its actual lane dependency map. Exact
   dependency equality permits scoped reuse with original run/hash/exit identities.
   A changed executed dependency requires fresh evidence for that capability.
   A historical artifact may be reused by hash without claiming its producer is
   current. Incomplete dependency knowledge remains pending, not "unaffected."
4. Validate fixed schema, nonempty bounded maps, lowercase SHA256 format, canonical
   safe relative paths, no case aliases, traversal or reparse paths, required path
   coverage, accepted-input anchor and toolchain/profile pins. Compare actual bytes
   against the frozen expected map before preparation and before launch. Capture
   source copies and generated project/runtime snapshot hashes.
5. Execute only lanes selected by that classification, serializing engine ownership.
   Every new invocation, capture, service preparation and repair record carries the
   new execution-binding hash. Preserve source checks after completion as well as
   input/report/process postconditions. A source change invalidates the candidate
   generation and creates a fresh run ID; it never updates an earlier evidence map.
6. Assemble a new dependency bridge joining historical input provenance, fresh runtime
   evidence and exact-current reusable lanes. Freeze its source/review/raw closure,
   keep all failed attempts, and submit the final GT06 package to two independent
   critics on that same final closure. Their new verdicts are required by the plan;
   this design and worker reviews supply none.

## Evidence needed and scope of reruns

| Lane or claim | Minimum disposition |
| --- | --- |
| Original art, original GT05 export semantics and accepted historical import | Preserve exact bytes and original acceptance. Verify the consumed artifact links; do not label old execution current or redo unchanged art simply because replay now has a new source map. |
| Binding reader/closure collection | Focused positive and negative tests: altered input/manifest/binding/source rejected; omitted required or dynamic dependency rejected; path alias/traversal/reparse rejected; different backend/repair/native closure rejected; post-freeze mutation rejected; old logs cannot acquire a new binding hash. |
| Shared Job fix | Reuse S131's exact-bound unit and native Python success/rejection evidence only if its full lane dependencies still match. New binding code does not by itself require rerunning unrelated Job tests; changed dependencies do. These tests do not replace native functional lanes. |
| Fixed import, menu/input, pause/resume, interaction/camera, capture and perf export | Fresh affected GT06 native execution on current binding, using the accepted asset. Retain trace/seed, snapshot, native report/PNG bytes, window/PID/time, actual target/helper exits and Job/handle cleanup. Intentional Stop stays distinct from natural exit. |
| Authenticated service, Stop, saturation, revoked-result, stale-capture and reviewer interaction | Remint affected lanes where shared Job/core transport or service dependencies differ. Reuse UI-only observations only with exact UI closure and a documented fresh runtime/service bridge; do not transfer old end-to-end behavior wholesale. |
| Managed fault → authenticated repair → replay | The conservative small route is a fresh complete causal lane because Job and core transport participate in it. Keep old fault/repair receipts as historical evidence. New request/response/receipt, selected-script bytes, native readback, immutable replay and same trace/GLB link must form the new chain. |
| Current GT05 staged publication | Not established by this replay refresh. If claimed, the existing strict verifier requires current-source runs for each affected stage; because `HOST` includes `cli_job.py`, it may require broad pipeline remint. Do not use historical mode, trim `HOST`, or route publication through the replay binding. |
| GT06 benchmark | The prescribed complete fresh campaign and gates remain unchanged. Host-only/partial diagnostics cannot become dataset rows. A runtime change intersecting its closure requires its own new campaign generation; report-only changes do not. |

Capture actual host exits and resource ownership independently, including UNKNOWN
when proof is unavailable. New verification may re-read old raw data under a clearly
named supplemental verifier scope; it cannot turn old source execution into new
execution. Keep exact-file, source-map, canonical JSON and Git blob hash domains
explicit; the repository's line-ending history makes these distinctions material.

## Fastest correct sequence

Finish and preserve S132 measurement first. Then do one bounded dependency/delta
pass, implement the single dual-binding boundary and freeze it once. Run focused
binding regressions and affected native functional lanes, reusing exact unchanged
evidence. Return to the benchmark only when the coordinator has a distinguishing
diagnostic conclusion and a frozen candidate, without changing its gates. Finish
with one complete evidence join and two new final critics. Do not open GT07 or claim
GT06 acceptance from this preparatory work.
