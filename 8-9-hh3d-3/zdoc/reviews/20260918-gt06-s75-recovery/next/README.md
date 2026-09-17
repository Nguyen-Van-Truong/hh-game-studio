# S75 next-campaign dependency readiness

Preparation only, 2026-09-18 Asia/Saigon. Suggested fresh campaign ID:
`gt06-s75-campaign-01`. The final coordinator-frozen working source compared
here has 49 runtime files and closure
`638304f54851366ac2a79a792a8009406fc927c3c6c410ad8f65cc2dd9b14995`.
This is a working-source snapshot, not a claim about a future Git commit,
campaign completion, critic verdict or GT06 acceptance. GT06 remains current;
GT07 is not opened. Only files in this `next/` directory were authored here.

The final source differs from S73's
`6f5d4c8a14ef8476c4cff6afb06ab161b17905f8593f9a685cd235593d7ee913`
at exactly three runtime paths, with no added or removed paths:

- `tests/replay/run_native_benchmark.py`: prepares the evidence `.gdignore`
  marker and checks it as part of the native fixture manifest.
- `tests/replay/benchmark_native.gd`: checks the exact marker bytes before
  effects, including rejection of BOM/newline variants.
- `tests/replay/benchmark_assembly.py`: adds the marker to the required project
  set and checks its exact bytes during assembly.

The assignment initially covered two files. The coordinator then found that
the assembly's exact nine-file set also required the marker and supplied the
final three-file freeze. The separate changed unit file
`tests/replay/test_benchmark_assembly.py` is in the broad review-runner map,
not the runtime49 map. Source/profile/toolchain checks were stable during this
preparation; the profile and toolchain hashes are unchanged.

`affected-dependency-bridge.json` records every per-file difference and 14
complete declared-map projections. These are source-byte checks, not another
execution of historical tests or a complete raw evidence audit.

| Evidence lane/domain | Comparison | Next action |
| --- | --- | --- |
| Benchmark campaign | Runtime49 changed at three paths | Remint the entire prescribed ten fresh host/editor pairs × 35 batches on the final source. No S73 partial measurements may enter it. |
| Benchmark native/assembly validation | Those three runtime dependencies changed | Bind final-source positive native marker, exact-byte negative marker and missing/coherently altered/BOM/CRLF assembly checks. Coordinator owns these runs; this preparation claims no results. Diagnostic and campaign closure counts remain separate. |
| S73 HTTP complete, HTTP Stop, saturated Stop, revoked result, stale capture | All 173 declared runtime bytes match current in each of the five lanes | Reuse the original five lanes and their full raw/owner/exits; no new service remint required for this benchmark-only fix. |
| S73 service review runner | 148 declared files; four differences: three benchmark files plus the assembly test | Preserve the original review map. Do not call the entire 148-file map exact-current or claim the old broad test run covered the new fixture/assembly. The unaffected runtime173 projections justify scoped service reuse. |
| S69 managed replay | All 159 declared bytes match current | Reuse scoped functional replay while preserving original S69 generation and S65 repair02 causal provenance. |
| S68 reviewer complete/Stop UI | Both five-file UI maps match current | Reuse original UI captures/observations. Their runtime173 maps differ only at the existing S73 `verified_journal.py` change, bridged by the five S73 service remints. |
| S69 three service adversaries | Each old runtime173 differs only at that same journal dependency | Keep historical provenance; use S73 remints for the changed current service behavior. No extra S75 remint is caused by this fixture fix. |
| Accepted GT03–05 and original fault/repair history | No gate reopening or new signature is claimed | Preserve original scoped accepted packages and exact dependency references. |

The five S73 service runtime map files retain SHA256
`d09916f43504aaba9a440cdadd59859ac7e7ca24c307ae3b99f4275feeb6dc95`.
Their map closure is separately
`fbc305e145489a7f0b07ef978fb471e290c96a0fe4328bd6ef78ba3e35b1d7b6`.
Neither is the benchmark49 closure. The service verification manifest's
recorded 158 checks and 1,281 raw files are inherited evidence, not newly
executed results. Keep the two intentional Stop lanes' native exit null;
outer exit0 does not become natural native exit0.

The causal chain remains S65 fault `gt06-s65-native-04` → authenticated GT03
repair `gt06-s65-repair-02` → S65 replay `gt06-s65-native-05` → S69 managed
replay `gt06-s69-managed-replay-01`. Named raw links were byte-checked for the
fault/repair/replay captures and selected configuration, and the original
`gt06.repair.move-speed` request/response digest link was checked. This does
not replace receipt semantic validation or a final complete raw audit.

Keep response hash domains distinct: `repair.json#/response_sha256` binds
the 726-byte `response-wire.json`, hash `46cfef5a866833af5760907fc2d896dab6115c1271a4cd4aefc23a81a0f92d74`.
The 727-byte newline-terminated `response.json`/lookup/retry copies instead
hash to `325079c574e7373e2f867315fc8ecea201a08ade474259afec361b5fc36cac82`.
The initial preparation stopped at an assertion that incorrectly treated the
copy as the wire; its exit1/stderr remain in `preparation.*` and
`preparation-host-exit.json`. The corrected preparation actual exit0 is in
`preparation-02-host-exit.json`. No original artifact was changed.

`collection-recipe.json` and `verify_campaign_readonly.py.draft` rebind the
historical S73 drafts to this candidate and retain the unchanged workload,
profile, thresholds, source checks and BoundRun/ownership verification. The
adapter was syntax-parsed only and **not executed**. Its revision field is
null; the actual named checkpoint proof remains pending. Historical S73 draft
reviews do not transfer to these new bytes. `preparation-check.json` records
the source check and generated artifact hashes.

Critical path:

1. Coordinator finishes final-source affected native/negative/assembly checks,
   confirms clean owned exits and freezes/checkpoints the exact49 map. Any
   source change invalidates this candidate binding and requires a new bridge.
2. With prior attempts terminal and Stop/ownership checks satisfied, coordinator
   may launch the fresh S75 campaign; this preparation performs no launch or
   automation change. Retain S73 launch1 RSS/status-gap and launch2 retained
   counter failures under original IDs. No repaired-cause or pass claim follows
   from a positive diagnostic alone.
3. If collecting supplemental telemetry, follow `telemetry-plan.md`: known
   owned PID + exact FILETIME + executable identity first; one disclosed
   external window of at most 120s at 1s intervals. Preserve observer overhead
   and actual exit separately; do not alter benchmark gates or baseline.
4. Only after complete terminal evidence, run the reviewed read-only adapter
   with pinned Python, collect real exits and all supervisor launches, verify
   actual checkpoint bytes, and seal the final source/review/raw requirement
   package. Two independent critics must bind the same final manifest/source
   before coordinator acceptance. Permission to progress does not waive gates.

No engine, test, campaign validator, scheduler action, automation, production
source, plan, Git staging or commit was initiated by this preparer.
