# GT06 S70 critical path and packaging prerequisites

Read-only planning/evidence review; this report is the only authored file.
Observed 2026-09-18 01:07 Asia/Saigon, HEAD
`e469f58dd2487d103a3e91ed77d7f4bba01f4f7a`. No source/plan edits, tests,
engines, future-gate implementation or acceptance verdict. Authority remains
`zdoc/8-9-godot-blender-agent-studio-plan.txt` S69, `CURRENT_VALID_WP=GT-06`.
Paths are relative to `8-9-hh3d-3/`.

## Current conclusion

The critical path is reliable ownership of the long benchmark, then its exact
full dataset, final evidence closure and two independent critics. The functional
native lanes already mapped to GT06 do not need speculative reruns.

The coordinator reports `gt06-s69-campaign-01` stopped during batch index 1 when
the tool session ended. Read-only inspection confirms `command-00.json`,
`command-01.json` and `joint-00.json` exist, but the attempt has no final capture,
cleanup or parent-failure record and neither host-owner nor editor-host has a
process-exit capture. It is **not a complete run and not benchmark PASS**. The
launch record's RUNNING value is historical. These facts do not diagnose an
engine fault or establish actual exits. Preserve this prefix; do not splice its
samples into another process pair or synthesize cleanup from process absence.

## Exact remaining GT06 work

1. **Finish the owner/launcher fix being handled by the coordinator.** Preserve
   ownership, bounded Stop and real terminal/cleanup records across the relevant
   execution boundary. Check changed paths with focused regressions and a bounded
   lifecycle proof, then freeze those dependencies. Do not lower the 7410-second
   per-run owner cap, bypass capture-v2 handle proof, hide a stopped run as success,
   or treat a hidden window as durable ownership.
2. **Run the locked full benchmark on the fixed closure.** Ten sequential fresh
   host/editor process pairs; each pair retains its processes for five excluded
   warm-up batches and thirty measured batches. Each batch has 1000 mock commands
   (500 inspect, 300 validation rejects, 200 admitted queue) and 100 actual
   create/undo/save/reload cycles. Total: 350,000 commands/35,000 cycles, including
   300,000 commands/30,000 cycles measured. No partial-run sample reuse. Complete
   verified runs may be resumed only under the same source/profile/workstation and
   with no persisted Stop; no qualifying complete S69 run is present here.
3. **Validate outcomes, not only completion.** Retain raw rows and run boundaries;
   median/p95/p99, inspect and Stop receipt p95 ≤500 ms, status gaps ≤2 s, no
   duplicate/lost effects or steadily increasing leaks, RAM growth ≤10% against
   the declared warm baseline after ten repetitions. Record quiescent/GC/import
   phases and OS-cache context, actual editor/host counters, real exits, Job-zero
   and wrapper/probe-handle closure. Stop receipt and final process drain are
   different observations. Serialize native/heavy work during measurement.
4. **Assemble the final GT06 review package.** Follow TQ00's
   requirement → test → artifact/hash mapping for GT06, section 2.6, TQ06 and
   TX02/05/13/18. Bind final source/tool/schema/profile/workstation identities,
   driver/verifier dependencies, logs, raw artifacts and actual pre/postconditions.
   The 46-file benchmark closure is not the whole GT06 acceptance closure.
   Fail closed on missing/stale evidence, unexplained warning/error/leak, or
   unproven cleanup. Retain a reproducible evidence inventory and actual available
   raw artifacts; copied summaries do not replace `studio/.local/` evidence.
5. **Obtain two independent reviews of the same final candidate.** Resolve concrete
   findings and recheck only affected dependencies; source changes after review
   require review of the changed candidate. Coordinator acceptance changes the
   first open plan row only after all dependencies/Verify/DoD are satisfied.
   Implementation reviews and old gate signatures are not those two verdicts.

The final package must carry these already-established functional proofs without
inflating their scope:

| GT06 requirement | Evidence to retain / final linkage |
|---|---|
| Blender edit → validated GLB → Godot import/readback → real Play | Accepted GT05 manifest `zdoc/reviews/20260917-gt05-s63-audit/manifest.json`, exact accepted GLB binding in `studio/host/replay/native_runner.py`, and GT06 runtime captures. Explicitly join producer/edit/import artifacts to the consumed hash; do not reopen GT05. |
| 60 Hz seeded input and real menu/move/outfit/emote/prop/pause/resume/quit; simulation frozen/UI advancing; PID/source/time/camera capture | Retain S68 reviewer complete02/stop02 and S69 managed-replay01. Historical inspection is labeled historical; seven stills do not imply a live debugger or HH World quality. |
| Seeded fault visible before typed repair and absent after replay | Preserve S65 native04/repair02 causal proof plus S69 managed replay using the verified repair receipt. Repeating the successful mutation is unnecessary. |
| Versioned raw-frame perf export, p50/p95/p99, 1% low and declared counters; missing schema/1% low rejected | Retain unchanged schema/exporter evidence and its tests. Screenshot-inclusive performance exports are diagnostic, separate from the tools UX benchmark. |
| Congestion, revocation, stale capture, Stop/no hidden reconnect resume and reviewer next action | S69 saturated-stop/revoked-result/stale-capture results, S68 GUI evidence and unit coverage. Saturated Stop has `STAGE_STOPPED` plus checked ownership, not natural native exit 0. |
| Source-dependent tests and ownership corrections | S69 full 434/434 precedes the final Stop-boundary fix; later 66/66 affected tests supplement it. Do not add overlapping counts or assign the earlier full inventory to later source. Future owner changes require only their affected verification. |

`zdoc/reviews/20260918-gt06-s69-owner-review/integration-followup.md` records the
read-only verification of 1124 raw hashes, current-source S69 adversaries/managed
replay, unchanged S68 GUI dependencies and resolved initial owner findings. Its
scope is implementation mapping. New changes still need their own dependency
comparison; no additional missing functional native lane was identified here.

At the GT06 review, record the existing `INTERNAL_FIRST_OSS_READY` positioning
and the OSS decision item explicitly. This does not authorize public signing,
publication, external installation or implementation of later gates.

## GT07–10 prerequisites and external dependencies

| Gate | Required predecessor and later acceptance work | Hard external/environment prerequisites; avoid invented blockers |
|---|---|---|
| GT07 | GT05 + GT06 ACCEPTED. Real multi-writer FIFO/expiry/fencing, active-manifest cross-app activation, manual-edit reconciliation, crash/ACK phase matrix, file/disk/journal failures, Stop/fairness and two critics. | Existing supported editor/Blender/OS fixture environment and permission within that fixture scope. The plan introduces no mandatory cloud account, paid service, production secret or physical Android prerequisite for GT07. |
| GT08 | GT07 ACCEPTED. Clean Windows/Android export and Linux-headless launch, pinned templates/toolchains/cache, negative build/supply-chain tests, local signer, ABI/4 KB/16 KB compatibility, two critics. | **At least one authorized supported physical Android device**, with SKU/OS and actual install/launch/runtime evidence. A reviewed SDK/adb/JDK/build profile and supported Windows/Linux execution are also necessary. S66 preflight found scoped SDK/adb gaps; device attachment/authorization remains unverified, not proven absent. Verified template archive/Linux helper presence is preparation, not GT08 acceptance. Emulator may support ABI/page-size proof, never replace physical runtime/GPU evidence. |
| GT09 | GT08 ACCEPTED, including physical Android. Actual declared client/model/host/version conformance, brief-to-repair/replay, reconnect/context reset, prompt-injection/capability tests, measured pinned MCP compatibility spike and two critics. | Access/authorization/quota for the clients/models actually claimed SUPPORTED. Do not invent evidence for unavailable variants or silently change model. External adapter code must be pinned and independently proven; research/README claims do not grant capability. No requirement to wait for HH World or claim every client. |
| GT10 | GT09 ACCEPTED and GT08 evidence retained. Clean-copy install/upgrade/rollback/uninstall, compatibility and one roundtrip/Play, trusted manifest verifier, notices/SBOM/help/runbook, two critics. Targets remain Windows/Android/Linux-headless; monetization OFF with artifact scan, no game capacity claims. | Local test trust key/pinned verifier and authorized fixture copies suffice for planned acceptance. **Production signing credentials, public upload, payment integration and game closed alpha are not prerequisites.** Public release/signing/legal decisions are separate owner gates. Physical Android remains an inherited hard requirement, so no desktop-only shortcut to GT10 or H2-P0-01. |

Keep GT08's producer build/verifier slice (TQ08-B/TX16-C) separate from GT10's
consumer install/update slice (TQ08-I/TX16-I); do not create a circular dependency.
GT10 later packages `HH-STUDIO-0.1`, including the perf schema and naming
convention, tool/source/artifact hashes, actual capability matrix, limits,
compatibility/deprecation and recovery commands. This report opens none of those
future implementation scopes.

## Progress text safe to archive or replace

Archive with its original bytes, source references and `AUTHORITY=0`; never
delete failed evidence or edit historical verdicts. Keep the live table,
`CURRENT_VALID_WP`, gate specs, TQ/TX contracts, policies, accepted refs and latest
remaining-gap summary authoritative. No archive operation was performed here.

| Current text | Safe maintenance action |
|---|---|
| Long accepted GT01–05 result/count narrative before GT06 | Move detail to a dated history snapshot; keep concise ACCEPTED rows, accepted commit/closure and evidence links. Do not rerun accepted dependencies simply to rewrite prose. |
| S65/S66/S67 successive unit counts, intermediate GUI closures and initial repair/service milestones | Archive chronology. Keep one concise functional coverage summary linked to the original causal repair proof, S68 GUI and S69 affected remints. |
| “Benchmark đang xây driver” and “đang đo batch1000lệnh đầu” | Stale current-tense wording: the combined driver exists and a combined batch has run. Replace with the actual blocker: sustained owned execution/full dataset still unproven. Preserve diagnostic01/02 source-hash lessons in history. |
| S68 347/48 then 415/62 counts, command-only residency narrative and single-run latency figures | Archive details with failed-run links. Keep short current warnings: diagnostic only, no inferred p95, no failed-prefix reuse, no changed thresholds. |
| Old requirements-map requests for adversary/replay remints and “unfixed” initial owner blockers | Already superseded by `integration-followup.md`; retain the historical file unchanged and link the follow-up. Do not turn resolved work back into the current queue. |
| Plan/README's `gt06-s69-campaign-01` launch RUNNING observation | Preserve launch record; update the current status with the interrupted batch-1 prefix and missing exits/cleanup. Never rewrite it to PASS or infer a clean stop. |
| Repeated closed review-routing history and long S54–S68 lessons in the current overview | Archive chronological detail, retaining concise applicable rules: one writer, accepted dependencies, exact source binding, native serialization, bounded Stop, actual exits/handle cleanup and focused regression. |

A compact live summary can state: functional lanes retained and mapped;
434-test baseline plus 66 affected regressions have distinct source bindings;
durable benchmark execution/full measurements remain; final package and two
critics remain. This improves routing without changing any DoD or granting a
new acceptance claim.
