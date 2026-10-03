# GT06 Formal25 functional requirement map — review candidate

AUTHORITY=0. This is a requirement → verifier/test → evidence index for the
coordinator's final package. It is not an acceptance verdict, a critic signature,
or permission to tick GT06/GT07. Authority remains
`zdoc/8-9-godot-blender-agent-studio-plan.txt`, especially GT06 DoD, TQ00/TQ06,
O4.3/O4.4 and the final functional/dependency join at lines 692–695.
Paths below are relative to `8-9-hh3d-3/` unless stated otherwise.

```text
FUNCTIONAL_GROUP=gt06-f25-functional-20261003-03
FUNCTIONAL_EXECUTION_FILES=217
FUNCTIONAL_SOURCE_CLOSURE=9a9c9c42fa2be7dedf485b25c99245e92073f7b024909a8f72ec948f08219691
FUNCTIONAL_HELPER_FREEZE_FILES=234
GROUP_VERIFICATION_SHA256=a6b23ff2a4255c6e7d52e453d5d2ed8b9d99e4208cd80c16dd7feec5dbde6639
FORMAL_CAMPAIGN=gt06-o4-formal-25
FORMAL_SOURCE_FILES=64
FORMAL_SOURCE_CLOSURE=727f9039c1cc83239f5ef1daff13de5e92e37b5ba442e64be8341ca058800b58
F06_CURRENT_MANAGED_GROUP=gt06-f25-managed-20261003-02
F06_CURRENT_MANAGED_REPAIR_REPLAY=AVAILABLE_CURRENT_SOURCE_REVIEW_PENDING
FINAL_CANDIDATE_MANIFEST=studio/.local/reviews/gt06-f25-final-review-20261003-01/manifest.json
FINAL_CANDIDATE_SHA256=READ_SIBLING_manifest.sha256_AND_VERIFY_BYTES
INDEPENDENT_CRITIC_01=PENDING
INDEPENDENT_CRITIC_02=PENDING
COORDINATOR_ACCEPTANCE=PENDING
```

## Evidence and source domains

The seven fresh lanes are verified by the unchanged S133 helper
`zdoc/reviews/20260920-gt06-s133-functional/run_service_refresh.py`
(`verify_freeze`, `verify_lane`, `verify_stage`, `verify_outer`, `verify_existing`).
The adapter `zdoc/reviews/20261003-gt06-functional-refresh/run_refresh.py` supplies
fresh IDs, append-only admission records and independent source checks: the launch
observer checks its actual imported 71-file studio domain; with the two driver
files, group03 freezes 73 files separately from installed217 and helper234.
Formal25's benchmark domain contains 64 files. The collector inventories imported
modules, so its membership varies by driver; these domains are not interchangeable.

Group evidence is under
`studio/.local/reviews/gt06-f25-functional-20261003-03/`: `driver-freeze.json`,
`driver-source/`, `admissions/`, `terminal.json`, and `lanes/freeze.json`, frozen
`lanes/source/`, `lanes/run-started.json`, `lanes/execution-complete.json`,
`lanes/verification.json` and each lane's invocation/capture/verification/inventory.
The group terminal records seven verified lanes, actual adapter result 0 and
`cleanup_verified=true`; lane receipts, rather than that aggregate flag alone,
supply actual process and Job evidence. All seven use installed217 above with
`source_unchanged=true`.

| ID | Fresh raw root under `studio/.local/reviews/` | Actual probe and result |
|---|---|---|
| HCOMP | `gt06-f25-http-complete-03/` | `tests/replay/run_service_probe.py --mode complete`; `http-probe/result.json`, 97 named checks including bound lease, native postcondition commit, dedupe, historical inspect and hash-bound capture. |
| HSTOP | `gt06-f25-http-stop-03/` | Same probe, `--mode stop`; `http-probe/result.json`, 12 checks including Stop latch, no reconnect resume, no fake commit and owned-tree drain. |
| SAT | `gt06-f25-saturated-stop-03/` and sibling `-outer/` | `tests/replay/run_service_adversary.py --mode saturated-stop`; `http-adversary/result.json`, 15 checks, two real held work connections, lookup/Stop response and no second runtime. |
| REVOKE | `gt06-f25-revoked-result-03/` and sibling `-outer/` | Same adversary, `--mode revoked-result`; `http-adversary/result.json`, 18 checks: revoked bearer denied, control-only grant cannot replay, result remains UNKNOWN and no second runtime. |
| STALE | `gt06-f25-stale-capture-03/` and sibling `-outer/` | Same adversary, `--mode stale-capture`; `http-adversary/result.json`, 17 checks, plus `intentional-capture-mutation.json` with retained original/mutated bytes. The mutated PNG is negative-test evidence, not a fresh positive capture. |
| GUI | `gt06-f25-reviewer-complete-03/` and sibling `-driver/` | `tests/reviewer/run_reviewer_probe.py --mode complete`; `reviewer-probe/result.json`, `observations.json`, `source.json`: actual Play keyboard action, Inspect/Capture buttons and window close. |
| GUISTOP | `gt06-f25-reviewer-stop-03/` and sibling `-driver/` | Same reviewer probe, `--mode stop`; actual Play/Stop keyboard actions and window close. These GUI flags are verified explicitly; the helper's numeric `checks=0` is not zero GUI coverage. |
| MANAGED | `gt06-f25-managed-20261003-02/` | Current wrapper `zdoc/reviews/20261003-gt06-functional-refresh/run_managed.py` uses the historical S138 helper/verifiers. `managed/freeze.json` binds installed217; `driver-freeze.json` freezes its separate 77-file driver/import domain. Retain `admission-repair/0001/`, `admission-replay/0001/`, `managed/repair/verified.json`, `managed/replay/verified.json`, outer invocations/captures/owner logs and frozen source copies. |
| REPAIR | `gt06-f25-managed-repair-02/` | Authenticated `script_text.replace`; `request.json`, `response-wire.json`, durable lookup/retry receipts, before/after state, selected config/manifest, `native-readback.json`, `validator.json`, editor identities/close receipts, `repair-terminal-cleanup.json`, `repair.json` and `capture.json`. Current installed217, source unchanged. |
| REPLAY | `gt06-f25-managed-replay-02/` | Immutable native Play using the selected repaired config; `capture.json`, `repair-replay.json`, runtime snapshot/source map, raw report/trace/captures/process metrics and import/runtime captured stages. Current installed217, source unchanged; original S65 fault provenance remains historical. |
| GT05 | `zdoc/reviews/20260917-gt05-s63-audit/manifest.json` and `20260917-gt05-s64-acceptance/acceptance.json` | Accepted historical producer/consumer inputs. Current functional bindings consume the same GLB; GT05 signatures do not become GT06 signatures. |
| PERF | `gt06-s65-native-04/perf-export-v1.json`, `gt06-s65-native-05/perf-export-v1.json` | Historical native reports/process metrics, with unchanged three-file exporter/schema scope. Index: `zdoc/reviews/20260917-gt06-s65-progress/runs.json`. |
| FORMAL | `gt06-o4-formal-25/` and sibling `-supervisor/` | Two fresh 35-batch pairs, strict assembly and run/campaign verification. Tracked index: `zdoc/reviews/20261003-gt06-formal25-critic-package.md`; read-only verifier: `studio/.local/reviews/gt06-o4-formal-25-critic-package/verify.py`. |

For each seven-lane runtime root retain `source-files.json`, captured source bytes,
runtime snapshot, `project/input/trace.json`, `project/out/report.json`, captures,
process metrics, and `import-host/` / `runtime-host/` start/capture/exit/cleanup/Job
artifacts. Retain applicable sibling outer/driver captures and logs. The helper's
selected inventories do not authorize deleting or substituting the original raw.

MANAGED's two `verified.json` receipts and both REPAIR/REPLAY source maps match
the same installed217 freeze. Preserve the managed 77-file driver domain separately
from group03's launch71/driver73, helper234 and Formal64 domains. Neither managed
admission result alone nor an aggregate terminal file replaces the per-lane proofs.

## Exit and Stop distinction

All seven outer owners have independently captured actual exit 0; all imports
have actual native exit 0. HCOMP, REVOKE, STALE and GUI also have observed runtime
exit 0, `completed=true`, wrapper 0. Their runtime Job records are zero/closed,
untainted, with no retained handle.

HSTOP, SAT and GUISTOP intentionally stop an in-flight runtime. Their recorded
runtime **actual natural exit is UNKNOWN** (`actual_native_exit=null`),
`completed=false`, wrapper exit **2**. Their Jobs are configured/assigned,
zero-observed/closed/untainted, with no retained handle or failed operation.
These establish the declared Stop/drain/ownership behavior, not natural runtime
exit 0 or successful gameplay completion. An outer exit 0 does not fill that
missing natural-exit field. Keep this limitation in the final review checklist.

MANAGED repair outer target 36416 and its repair child 13740 have captured actual
exit 0, helper exits 0 and verified owned trees. Repair cleanup records both known
editor targets 29968 and 19712 with actual exit 0, wrapper 0, no held handle,
zero/closed/untainted Jobs, owner/transport closed and no cleanup error. These are
the captured editor-close results; this map does not add an unrecorded natural-exit
classification. MANAGED replay outer target 31284 has captured actual exit 0;
import 14340 and runtime 49180 have actual exit 0, wrapper 0, `completed=true`,
`natural_tree_exit=true`, zero/closed/untainted Jobs and no retained handle.

The standalone repair report deliberately has `runtime_repair_proven=false`:
editor repair/readback alone cannot establish gameplay effectiveness. Likewise,
`replay_checks.managed_repair_proven=false` and the nested standalone observation
in `managed/replay/verified.json` describe one run, without asserting its repair
relationship. The outer `repair-replay.json` records **`managed_repair_proven=true`**
after binding the original fault capture, current repair capture, selected config,
same trace/GLB and current replay capture. Fault movement is 0 m; replay movement
is 1.50000023841858 m versus expected 1.5 m, with all replay postconditions true
and the movement fault absent. These fields retain their original values/scopes.
REPLAY's native capture `public_ack=false` is also a standalone capture scope;
the mutating command's `COMMITTED` / `GODOT_MANAGED_SCRIPT_REPLACED` public ACK
is recorded in REPAIR's response wire/receipt with `postconditions.public_ack=true`.

## Requirement → test/verifier → artifact map

Tests below identify regression contracts, not new executions by this document.
Their invocation/source receipts must be joined separately; do not sum overlapping
suite totals. `AVAILABLE` means bounded evidence exists for review at its stated
source scope. It does not mean the requirement or GT06 is accepted.

| ID / requirement | Concrete test or verifier | Evidence, source scope and remaining boundary |
|---|---|---|
| F01 / vertical slice and accepted dependency | `host/replay/native_runner.py:accepted_inputs`; helper `verify_freeze` / `verify_lane`; managed helper `verify_replay_chain`; `tests/replay/test_repair_replay.py` | **AVAILABLE FIXTURE CHAIN, REVIEW PENDING:** historical accepted GT05 producer/input hashes → current HCOMP/GUI import/native Play → historical S65 zero-speed fault → current REPAIR authenticated typed mutation/public readback/ACK → current REPLAY gameplay postconditions. Installed217 and MANAGED's own frozen driver/source receipts bind the new execution. Preserve each historical asset/fault source domain; this demonstrates the declared GT06 fixture, not a shipped authored game or a fresh Blender editing session. |
| F02 / fixed 60 Hz, seed and pressed/held/released through real input/menu | `host/replay/trace.py:validate_trace`; `observation.py:validate_observation`; `tests/replay/test_trace.py:test_schema_version_and_fps_are_exact`; `test_observation.py:test_input_event_callback_and_real_menu_button_are_required` | **AVAILABLE:** HCOMP/GUI completed native report, authored trace and runtime bindings at installed217; trace anchor below. Bind actual run/command/PID/window/snapshot and postconditions. GUI keyboard flags supplement, rather than replace, native callbacks. |
| F03 / movement, outfit/emote/prop, pause/resume/quit | `observation.py:validate_observation`; `tests/replay/test_observation.py`, including `test_pause_body_animation_and_simulation_changes_rejected`, UI advance/resume/quit checks | **AVAILABLE:** completed HCOMP/GUI native report and captures at installed217. Preserve post-transition state, interaction world hit and paused simulation versus advancing UI. Intentional Stop lanes are not complete quit/gameplay evidence. |
| F04 / bounded inspector, scene/property/runtime and historical state | `tests/replay/test_inspector.py`; HCOMP `bounded_historical_inspector`; GUI helper `GUI_INPUT` / `GUI_CLOSE` checks | **AVAILABLE:** HCOMP `http-probe/` inspection outputs; GUI `reviewer-probe/observations.json` and native result at installed217 plus reviewer source map. Historical observation is labeled as historical; no arbitrary live-debugger capability is inferred. |
| F05 / camera/bookmark/capture freshness, TX13 identity/source/time | `tests/replay/test_observation.py` PID/window/frame/camera/PNG checks; helper `MUTATION_WITNESS`; STALE named rejection checks | **AVAILABLE:** HCOMP hash-bound menu capture, GUI Capture action, native report/capture bytes and STALE mutation witness at installed217/helper234. Preserve original versus deliberately mutated PNG and fresh/stale result distinctions. |
| F06 / seeded fault → authenticated typed repair → causal replay | `host/replay/repair.py:verified_fault`; `repair_replay.py:verified_repair`; `observation.py:validate_observation`; managed helper `verify_replay_chain`; `tests/replay/test_repair_replay.py` | **AVAILABLE CURRENT SOURCE, REVIEW PENDING:** MANAGED/REPAIR/REPLAY at installed217. Original S65 fault capture → repair capture `e49a4522…` → selected config `4fe3141b…` → replay capture `4ff63ca5…` / causal report `93201023…`. Public ACK follows managed editor readback; same trace/GLB replay removes the movement fault and passes actual input/menu/interaction/pause/resume/quit/capture postconditions. Actual exits and cleanup are enumerated above. Top-level causal `managed_repair_proven=true` does not overwrite the standalone observer's false field. S138 remains original-source historical evidence. |
| F07 / perf schema/raw frames/quantiles/1% low/counters | `host/replay/perf_export.py`; `tests/replay/test_perf.py`; `test_perf_export.py:test_missing_readiness_remains_gap`, `test_unavailable_measured_counter_not_filled` | **AVAILABLE HISTORICAL NATIVE / UNCHANGED COLLECTOR:** PERF envelopes `HH-GT06-PERF-EXPORT-1`, artifact schema `hh-studio.perf-collector` 1.0.0, original native154 provenance and collector3 below. Keep startup unavailable values, counter semantics and screenshot overhead explicit. This is not Formal25 UX performance or a current native remint. |
| F08 / authenticated admission, postcondition ACK, dedupe and UNKNOWN | `tests/replay/test_service.py`, `test_verified_journal.py`, `test_journal_index.py`; HCOMP named commit/dedupe checks; REVOKE named denial/UNKNOWN checks | **AVAILABLE:** current HCOMP/REVOKE durable result/journal/receipt artifacts and raw bindings at installed217. Preserve accepted-pending versus committed versus UNKNOWN, grant/lease/digest and no-second-runtime proof; mock fixtures do not establish native effects. |
| F09 / reviewer UX, keyboard/error/UNKNOWN actions and no hidden resume | `tests/reviewer/test_model.py`, `test_app.py`, `test_client.py`, `test_client_adversarial.py`; helper `GUI_INPUT` / `GUI_CLOSE` | **AVAILABLE BOUNDED GUI:** GUI actual Play key, Inspect/Capture buttons; GUISTOP Play/Stop keys; REVOKE/HSTOP reconnect rejection. GUI five-file source closure below plus native installed217/helper234. Error/UNKNOWN UI edge cases retain unit-test scope; no human usability/playtest signature is supplied. |
| F10 / TX02 stale identity/context and save/reload | `tests/replay/test_inspector.py`; `test_native_benchmark.py`; formal native index/readiness/assembly verifiers | **AVAILABLE IN TWO SCOPES:** STALE/current inspector rejects stale capture/context at installed217; FORMAL supplies repeated direct fixture create/undo/save/readback/reload cycles at source64. Do not promote the synthetic benchmark into authored-product save/publication proof or hide private-state resets. |
| F11 / TX05 timeout/Stop/PID ownership and cleanup | helper `verify_outer` / `verify_stage`; `tests/replay/test_backend.py`, `test_process_probe.py`, `test_benchmark_job_owner.py`, `test_benchmark_stop.py` | **AVAILABLE BOUNDED:** seven current lane owner/identity/Job artifacts and FORMAL actual exit/cleanup proofs. Preserve the three intentional Stop UNKNOWN natural exits described above. General OOM/disk-full or every GUI owner exception is not newly injected by these seven lanes; applicable fault receipts need their own source join. |
| F12 / TX18 quota/congestion/retention/Stop priority, isolated Play | `tests/replay/test_transport.py:test_stop_isolated_from_blocked_owner_work_lookup_and_slow_control`; service/backend limits and reviewer deadline/retention tests; SAT/REVOKE/HSTOP checks | **AVAILABLE FIXTURE SCOPE:** SAT real two-connection work saturation, responsive control/Stop, bounded terminal drain and no second runtime; REVOKE/HSTOP deny replay/reconnect at installed217/helper234. Full multi-project fairness and recovery belong GT07. Short probe timings do not replace Formal25 distributions. |
| F13 / O1/O4 exact benchmark counts and latency/status/memory/effect limits | `tests/replay/benchmark_assembly.py:assemble_run`, `assemble_dataset`; `benchmark_profile.py:summarize_dataset`; campaign `verify_run_capture`; local FORMAL `verify.py` | **AVAILABLE BENCHMARK, REVIEW PENDING:** FORMAL two fresh pairs ×35 batches =70 retained samples, five warm-up +30 measured per pair, current profile v6 and source64. Each batch retains 1000 HTTP commands +100 direct native cycles. Strict assembly, counters/watchdog/status/exits pass per package; no partial prefixes from Formal01–24 enter this dataset. |
| F14 / sustained owned execution and safe final publication | FORMAL campaign/run-capture verifiers; `tests/replay/test_campaign_task.py`, `test_benchmark_campaign_stop_completion.py`, terminal-cleanup tests | **AVAILABLE BENCHMARK CLOSEOUT, REVIEW PENDING:** FORMAL request/XML/start/return, actual owners/import/editor exits, tree/Job/handles/watchdog and exact terminal Scheduler/deletion receipts. Retained O7 prerequisite is separately bound (49 batches, 1832.842787 active seconds). Scheduler/wrapper return alone is not process-exit proof. |
| F15 / final requirement/source/raw closure and two independent critics | This map; source/manifest/schema verifiers; O4.3 same-final-hash critic records | **PENDING:** finish every dependency/raw/test/schema/driver join, seal final manifest with accessible raw archives, preserve failures/limits, then two owner-dispatched independent read-only critics using different models on the same final hash. F06's execution evidence now exists; final sealing and acceptance review remain separate. No signature, tick or GT07 opening is supplied by this map. |

## TQ00 join and remaining proof

TQ00 requires the accepted dependency table, GT06 spec, section 2 and referenced
TQ/TX requirements to resolve to actual pre/postconditions, evidence hashes,
source/test/driver/verifier/schema closure, true exits and clean owned leftovers.
An orphan requirement is a GAP. The coordinator must join:

1. Current installed217/helper234 and adapter73/launch71 freezes to the seven raw
   roots, sibling owners and their lane inventories/verification receipts.
2. Accepted GT05 manifest and three input hashes to each consumed GLB/runtime
   snapshot; retain accepted GT05 historical authority without transferring signatures.
3. MANAGED installed217 plus its driver77/source copies and both admission/outer
   invocation/capture/verified receipts to REPAIR/REPLAY raw, selected config,
   public command receipt and the causal report. Bind the original S65 fault
   provenance separately from the new executed source; preserve nested observer
   scope, all captured exits and cleanup. Do not substitute S138 or claim a new
   fault run. Retain managed preparation attempt 01 with its original outcome.
4. PERF's original native input/source provenance and exact collector3 pins;
   historical raw is not relabeled as installed217 or Formal64.
5. FORMAL64/profile/dataset/summary/capture and Scheduler/ownership/O7 raw, with
   original failed campaigns/admission groups 01/02 excluded and retained.
6. Source-specific test invocations and any fault-coverage limits, the Stop natural
   exit UNKNOWN limitation, final immutable archive/manifest hashes, clean-log
   checks, lease/source integrity, two verbatim same-hash critic outputs and the
   coordinator decision. This draft contains no final acceptance result.

The concrete referenced gates resolve as follows; this is an evidence join, not
a claim that every possible failure in a TX family was newly injected:

| Gate | Exact evidence join / limit |
|---|---|
| TQ06 | HCOMP/GUI and REPLAY `project/input/trace.json` → bound report → native callback/menu/interaction/pause/resume/quit/capture checks. The same authored trace is fixed 60 Hz with seed 17 and explicit pressed/held/released edges; REPLAY ties it to selected repaired config and current snapshot/source. Direct methods are not the sole E2E proof. |
| TX02 | STALE intentional original/mutated capture witness and UNKNOWN/retry rejection; inspector expected-context tests; REPAIR request expected generation/revision/hash → before/after state, old/new editor identities, selected manifest and native script readback. FORMAL supplies its separately bound fixture save/readback/reload cycles. Each context remains tied to its actual source/PID/root/generation. |
| TX05 | HSTOP/SAT/GUISTOP latch/no-resume/no-fake-commit/owned-tree-drain proof with UNKNOWN natural exits; MANAGED and FORMAL captured actual successful exits and clean Jobs/handles. Timeout/owner exception tests and any reused fault receipts require their own invocation/dependency join; clean Stop Jobs do not establish unobserved natural exit 0. |
| TX13 | Separate editor/Play process identities; REPAIR old/new editor identity and readback/selected config → REPLAY PID 49180, retained Windows start identity, runtime snapshot, source/GLB/trace anchors and frame/time-bound PNG/report checks. STALE supplies negative capture freshness proof. Do not relabel stale PNGs, historical sources or wrapper ACK fields. |
| TQ00 | All F01–F15 rows, accepted dependencies and referenced gates → immutable source/test/driver/verifier/schema/raw manifests, true exit/cleanup receipts and explained limits → two verbatim same-final-hash critics → coordinator decision. The candidate manifest/hash are produced by build_review.py and must pass its byte/coverage check; both critics remain pending. |

No current F06 execution gap remains in the inspected receipts. Material final
review limits remain the three intentional Stop natural exits UNKNOWN, scoped
historical PERF/GT05/S65 reuse and applicable fault/test dependency joins. The
final byte seal is external to this document: see manifest.json and manifest.sha256
in the final-review packet. No acceptance critic is supplied by this document.

## Current-source regression receipts

No native engine or benchmark was rerun for these tests. Actual subprocess exits,
source-file maps, driver/invocation hashes and stdout/stderr are retained under
`studio/.local/reviews/gt06-f25-final-tests-20261003-01`, `-02` and `-03`.

| Suite | Authoritative receipt | Result |
|---|---|---|
| Protocol | group01 `protocol-exit.json` / stderr | 447 tests, 4 declared skips, actual exit0 |
| Replay | group02 `replay-exit.json` / stderr | 849 tests, 1 declared skip, actual exit0 |
| Reviewer | group02 `reviewer-exit.json` / stderr | 65 tests, actual exit0 |
| Linux executor | group02 `executor-exit.json` / stderr | 24 tests, actual exit0; execution binding/installed suites are already in replay |
| Admission wrappers | group03 `adapters-exit.json` / stderr | 13 tests, actual exit0; includes real kernel exclusion and consumed-ID rejection |

Group01 replay remains failed: the proof runner held the real global guard that
campaign unit tests attempted to acquire. Group02 gives only the child tests a
private LOCALAPPDATA namespace, retaining the parent guard on the real machine;
production code and policy were unchanged. Protocol was not repeated. Two group02
adapter tests then encountered already-consumed real native IDs; their test-only
raw namespace was isolated and a consumed-ID regression added. Group03 reruns only
these wrapper tests. Original test bytes are retained as group02
`test_managed.before.py`; all other declared test/source hashes remain unchanged.
These failures are visible evidence of harness/test isolation fixes, not erased
or recategorized native benchmark failures. Skips and scope remain explicit.

The packer derives required members from group03 selected inventories, frozen
source maps, repair artifacts and replay/historical runtime snapshots and captures.
A missing required-reference negative check was rejected without modifying raw.
Numbered ZIP members keep archive paths below 180 characters; the manifest maps
each back to its original relative path. Root public repair journal/events are
included; private owner stores and caches are excluded and retained locally.

## Small recorded anchors

These are producer/coordinator-recorded metadata anchors, not a new recursive raw
hash audit. Canonical source closure, raw-file SHA256, profile bytes and runtime
snapshot domains remain distinct; do not reserialize one domain as another.

| Anchor | SHA256 |
|---|---|
| Accepted GT05 manifest | `fd0b4a984c7bee261c083c07d461baf55325e936d66df2eeab897b422ee0a02b` |
| Consumed GT05 GLB | `e85e536137208ba84adbc875b6fb647b5a4e49156344e03e2e8947a7ae91e377` |
| GT05 input manifest / producer report | `1dfb3a3897c7471a0f1be22fde78d1bdc751823a5f6b9268c38d3e28c166665a` / `13a0416950aa2f6e4589442e1fa917c023bfe8395af717f803d1a1362fce8eee` |
| Authored 60 Hz trace | `c7d3d949e1aed9e1fc40a458c940640f3f88db9fbb965d669654ba5b58be8fbe` |
| Original S65 fault capture | `d3469bee92f7decad37d1f937631cff467548c8751f03ca99eac029c7547b7a1` |
| Current managed freeze file | `ed57a46893578c5728765ed14d1ce897469a842856c199c13407e66f1e2995e4` |
| Current REPAIR capture | `e49a4522962e3c9a062079550251ff654682617b4e6e2793f0d2a7bca50aca81` |
| Selected repaired config | `4fe3141b9afe6b411b585b203cebae77e851a406c291ac26620eb8cd7c018d90` |
| Current REPLAY capture / repair-replay report | `4ff63ca53048da5e322507da641052fd2804b194c67503a556a178f98317f167` / `93201023b6a2f1b44fbe73b3d9578f0eb867ff598c928a85792d554106c7a0f2` |
| Current installed binding file | `7bd657381817fe873214272f96e296f93a04d9f1608147399742a91bb36eda1c` |
| GUI source closure | `7665621f1090836c2bc711ccc7f6857c3961b99be5b077292baaadc933b712fb` |
| Historical S65 native154 closure | `58710f5d13a31190accfe8addb7fcb4885e3ee831a8a5152b4917cc9a103959f` |
| PERF collector3 closure | `7db13b1790e69ec225215cd309d54ccadf7ee629415d8b5bffb2769a53e35f0e` |
| PERF schema / perf.py / perf_export.py pins | `394d1df03bdfd736ea3fe9f260e9d718d35f3820cde35d1c45ccab65fbc24834` / `7c24c11989420e1600bcb20b8949fea44ea93b381bcab824e471465f5148edc7` / `d20c3b0505206cb4d5ba8fcbe5eede8281954d76b1757ce99f03cdb81bb017c2` |
| Native04 / native05 PERF export files | `6ef655c72cc1699affd2fadf03eb90f9ea2f259c468372d7637be428483b264d` / `56a5fc1771bebddcd237b66fb9037f565e57912328aa84323c86c9ff03d6af60` |
| Formal25 profile / dataset | `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35` / `3b0da65e10ea4425bd06d4c2ef7a446dde171a1e0b56fd125301ed1b6ea0a15a` |
| Formal25 summary / campaign capture | `9b8e70f91ac4c08cabe592c96387aa3d88ed01038788fc4a90dda19fe88e84a2` / `fb6c877d06667ddb293d3961bc90aa46ad43b48541a3c26e1d88cf1f84d1c914` |

Only this draft document was written for this assignment. No tests, engines,
Docker, raw-tree copying/hashing, plan/report/lane edits, commit or acceptance
review was performed by its author.
