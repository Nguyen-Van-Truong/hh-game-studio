# S76 independent performance-gate design review

2026-09-18, Asia/Saigon. **Design review only; no GT06 PASS, TICK or acceptance verdict.** Source is not a final acceptance candidate. Only this report was written. No runtime/plan edits, engine launch, test suite, campaign validator, scheduler mutation, process control, commit or further delegation was performed.

Observed repository HEAD: `dfbed1621a831abd9cc005f2b1ee01de9fec2702`. The initial status contained existing untracked review artifacts. The read-only process inventory showed no Godot or Blender process. Nested `AGENTS.md` routes this work to the tools plan, S76, `CURRENT_VALID_WP=GT-06`; Vault Fighters and HH World are outside this review.

## Finding: conservative gate, not an exact definition of leakage

The normative plan at `zdoc/8-9-godot-blender-agent-studio-plan.txt:873–890` requires ten process runs, five warmup batches followed by thirty measured batches, the fixed 1000-command mix and 100 native cycles, raw samples/quantiles, inspect/Stop p95 <=500 ms, status gaps <=2000 ms, no duplicate/lost effects or steadily increasing leakage, and stable RAM growth <=10% against warm baseline after ten repetitions. It also requires explicit phases/cache context and locks the metrics/device before execution. GT06/TQ06 additionally requires real input, pause, capture and causal repair evidence; this command benchmark alone does not fulfill those requirements.

The implementation operationalizes memory more strictly:

| Contract element | Current implementation | Interpretation |
| --- | --- | --- |
| Warm baseline | Exactly batch index4, same process identity; `benchmark_profile.py:16–20,181–184,245` and assembly baseline from `samples[4]` | Cannot select an earlier higher warmup, move baseline, restart the pair or add warmups after seeing results. |
| Handles, editor objects/resources | Every index5–34 value must be <= its batch4 baseline; `benchmark_profile.py:319–326`, `run_benchmark_campaign.py:256–270` | Stronger than the literal prohibition on steadily increasing leakage. A bounded transient or a later stable plateau can fail it. |
| RSS | Every measured RSS value <=110% of baseline; `benchmark_profile.py:323–324` | Stronger than testing only repetition10's stable RAM. The tenth measured value is reported but is not the only gated value. |
| Availability | Applicable missing counters become GAP/rejection, never zero or success | Correctly preserves uncertainty. Python-host ObjectDB/resources alone are explicitly inapplicable. |
| Cleanup | Actual host/editor exits, owned-tree zero and released wrapper ownership handles | Separate from live-process counter observations. Cleanup after exit cannot demonstrate absence of a leak during the workload. |

Thus **“the plan literally requires every sample's total handles <=warm baseline” is inaccurate**, but the frozen v2 implementation is a conservative, additional operational constraint rather than a permissive interpretation. The current plan's execution instructions explicitly preserve thresholds, reject counter subtraction/reset and forbid relaxing the gate (`:128–132,159,171–174,212–214`). This review does not authorize replacing it with a trend test, tolerance, average or final-idle check. The S75 failure remains a failure under its frozen contract.

The locked profile is `gt06-tools-ux-exact-v2`, profile SHA256 `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`. Its dataclass/hash contains workload and RSS settings, but the every-sample retained-counter comparator lives in validator/campaign source, not a separately serialized profile field. **Keeping PROFILE_SHA256 unchanged while weakening either comparator would still change the measurement contract.** Source closure and reviewed semantics must bind the rule. I did not verify a cryptographic profile signature or find an accepted GT06 verdict in this task; “locked profile” does not imply such a signature.

If a future owner-directed profile design wishes to measure persistent leakage differently, it needs an explicit prospective version/decision, independently reviewed sampling and failure rules, and a fresh full dataset. It cannot rehabilitate S75 or be presented as an equivalent v2 implementation. That redesign is unnecessary to continue the currently authorized unchanged-gate path.

## What the counters establish, and what they do not

`sample_editor()` (`run_benchmark_campaign.py:166–177`) records the target's total OS handle count through the retained process probe after native batch completion and before ACK. `NativeObserver.sample()` does the same for the host. Assembly (`benchmark_assembly.py:467–546`) binds the command/native/ready/start/joint/ACK artifacts and combines these OS observations with fresh native ObjectDB/resource counters in the ACK. This is a bounded phase sequence, not a simultaneous atomic snapshot of every counter.

An increase from577 to579 is sufficient to fail v2, but it does not identify two leaked handles. Conversely, a total that remains below baseline can mask leaked resources if unrelated startup handles close. A later net decrease does not prove every new handle was released. A numeric handle slot reused between snapshots is not a stable object identity. Flat ObjectDB/resource counts and falling RSS cannot decide which OS handle lifetimes persist.

The native “quiescent” phase currently proves a >=4-frame and >=1.1-second settling window plus semantic scene/root readback (`benchmark_native.gd:601–636`); it does not establish that all OS/library/background queues are empty. The existing PSS inventories contain192 entries without valid type metadata. They remain unclassified; they cannot be silently excluded from totals or assumed to have harmless ownership.

S75 batch8 also independently exceeds the progress gate: saved gap2016.2214 ms >2000. The retained-counter exception is raised before the later gap check, so a single failure code is not evidence that every other gate passed. Eventual COMMITTED readback after the connection-loss lookup preserves effect correctness but does not erase the status-gap failure. Preserve both findings.

## Accurate diagnosis while preserving the signed/frozen rules

1. Keep the official counts exactly as captured, at the existing batch boundaries, with same-PID/start/source/profile bindings. Do not subtract an assumed pool, replace RSS with private/peak bytes, take the minimum of repeated samples, wait until a favorable count appears, or change warmup, settling, deadline or mix to clear this failure.
2. Use separately labeled supplemental observations at predetermined boundaries and fixed idle times. Preserve pre/post/captured totals, every type addition/removal and unavailable entry, monotonic bounds, native frame/phase, semantic readback and actual observer/native cleanup. Existing diagnostics already provide much of this; analyze them before adding another helper or engine lane.
3. Attribute lifetime, not just net growth: compare all additions and removals across repeated equal workloads, and trace an anomalous type to its owning subsystem/task and completion condition. PSS type/name/thread metadata narrows candidates; without stable identity or creation/close attribution it cannot prove a particular Event/IoCompletion was retained or released. Do not label a CRT thread entry as its caller or “thread pool” as its proven owner. If existing inventories cannot discriminate, design one bounded owned-process follow-up around the concrete remaining hypothesis, leaving unknown attribution explicit.
4. Separate an intentional bounded resource from a resource that grows with repeated operations and survives its expected owner teardown. Require a mechanism/readback for an ownership fix. Also preserve real target exits and checked Job/wrapper cleanup; process disappearance, scheduler0 or forced termination is not equivalent evidence.
5. Verify an identified repair with focused affected checks and the unchanged profile. A diagnostic plateau, eventual drain, absent recurrence or overall slope near zero is supplemental evidence only. A complete passing v2 dataset and the other GT06 requirements are still needed; unexplained leak evidence must remain visible to the final critics even if total-count thresholds happen to pass.

The existing 8x100 retention run now has terminal files. I parsed `studio/.local/reviews/gt06-s76-retention-01/result.json`, its nine handle inventories/point files, and the outer retained capture; I did **not** execute the ownership verifier or perform a full raw manifest audit. Its report records native PID25368 exit0, Job active0/closed, and outer target37480/wrapper30776 exit0. Recorded pre/post/captured counts agree at every point:

| Point | Handles | Native objects | Resources |
| --- | ---: | ---: | ---: |
| batch00 | 573 | 71125 | 6 |
| batch01 | 565 | 71125 | 6 |
| batch02 | 565 | 71127 | 6 |
| batch03 | 557 | 71125 | 6 |
| batch04 | 559 | 71125 | 6 |
| batch05–07 | 559 | 71125 | 6 |
| fixed60s idle | 559 | 71127 | 6 |

This shows a flat559 tail in that diagnostic. It does not establish a leak fix, caller attribution or full-run acceptance. It has only eight native batches, added diagnostic coroutine/timer state, no1000-command HTTP batch, and no complete35-batch pair or ten-pair dataset. The idle object delta should not be transplanted into the official ACK measurement. All nine PSS files still report192 unclassified entries.

## Fastest legitimate critical path

**Reuse unchanged functional/service evidence; spend new runtime work on the unresolved benchmark.** I rehashed current files against all49 entries in `current-runtime-source.json`: zero mismatches, closure `ffa6071a1fb9d324da7cd860fb41b656e99135a3118367873c7399e85e8432fe`. I also read and independently compared every entry in the14 declared source maps from S75's `next/affected-dependency-bridge.json`, without running those lanes again:

| Existing evidence | Current byte comparison | Safe use |
| --- | --- | --- |
| Five S73 HTTP/native service lanes: complete, Stop, saturated Stop, revoked result, stale capture | Each runtime173 map unchanged | Reuse original scoped runtime evidence, raw provenance and actual exits, subject to final raw verification. No service rerun is justified by cadence-only changes. |
| S69 managed replay | All159 declared files unchanged | Reuse the original functional lane and S65 fault→repair02→replay causal chain. |
| S68 complete/Stop reviewer UI | Both UI5 maps unchanged | Reuse UI evidence with the original source label. Both larger runtime173 maps still differ only at `host/replay/verified_journal.py`; retain the existing S73 service bridge for that difference. |
| S69 historical service adversaries | Runtime173 differs only at the same journal file | Keep historical evidence and use S73 remints for current service behavior. |
| S73 broad review runner |148 files, **five** current differences | Do not relabel the whole old unit run as exact-current. Differences are benchmark assembly/native/preparer plus `test_benchmark_assembly.py` and `test_native_benchmark.py`. S75's report had four differences; S76 adds the latter test file. |
| S70/S71/S73/S75 benchmark partial attempts | No complete passing pair | Preserve failures; zero acceptance samples can be salvaged by joining attempts or changing their source label. |

These are byte/projection checks, not full dependency-discovery proof or renewed critic signatures. Final closure must retain data/schema/entrypoint dependencies and the original raw domains. Accepted GT03–05 need no reopening while their dependencies remain unchanged.

Recommended order:

1. Audit the already completed retention raw/cleanup and analyze the existing deltas. Reuse the cadence57-unit, native positive and five negative-guard evidence only after checking their complete affected dependency maps. Do not rerun engines merely to correct report fields.
2. Use the guarded cadence change and verified800-cycle diagnostic to decide readiness for the first full campaign on this source. A fresh fail-closed campaign can legitimately supply the missing long-run/full-mix evidence while handle caller attribution and the2016 ms recurrence remain explicitly unresolved; diagnosis need not become an endless prerequisite demanding proof of the campaign before running it. Existing30 HTTP inspections do not prove that gap repaired. Add another bounded diagnostic only if a specific unresolved fault makes the campaign unsafe or uninformative. Preserve journal validation/durability, lookup reconciliation and watchdog checks; do not declare the old failures solved in advance.
3. Freeze/checkpoint the final affected source and verify focused changes. Run a fresh exact campaign on that source, serializing native lanes and avoiding heavy parallel tests. The required work is10 fresh pairs x35 batches, each with1000 HTTP commands and100 native cycles, preserving7410s/run and all barriers/counters. The first full pair is already part of that campaign; there is no reason to run a redundant35-batch “preflight” pair if source and diagnostic readiness are established.
4. Resume only a **complete** verified run in the same frozen campaign/source/workstation/profile/slot, using the existing `verify_run_capture` path. `run_benchmark_campaign.py:369–423` already supports this; it does not authorize cross-campaign transplant, partial-pair continuation or retry until a favorable dataset appears. Keep every failed attempt and its cleanup record. Any runtime source change remints affected evidence and requires a new campaign binding.
5. Once terminal, verify full dataset/schema/hash/actual exits and assemble one final requirement→test→evidence package with the unchanged-lane projections. Obtain two independent reviews on the identical final manifest/source, then let the coordinator decide GT06. This review is not either final verdict.

## Static input fingerprints

SHA256 of exact bytes at review time:

| File | SHA256 |
| --- | --- |
| tools plan S76 | `d2949a341a3021942c4150873f46c1234d29eb9e04419cdf4ec62038a1120bc5` |
| `studio/tests/replay/benchmark_profile.py` | `ddbd98583060f791226fca83e275cf01204b37112627383198dcef4ec6f6f233` |
| `studio/tests/replay/run_benchmark_campaign.py` | `09f9d6a24c6281193f21c9aa89c48602ac5d70dfe86882fbaf76e8366c66dd6c` |
| `studio/tests/replay/benchmark_assembly.py` | `c1c6f67734e5e7feebae109ed7ce7d960fa578a8e1504ec5390c3620c6a65003` |
| `studio/tests/replay/benchmark_native.gd` | `61ca9916f9b8cf758e702b59bf05d316f7f12c6c491d54f788054761da385ea1` |
| `studio/tests/replay/run_native_benchmark.py` | `6919f07d0e148d03dd15a4804f42b5bf1aba427610af3533d87c5f3a691a3788` |

All paths in this report are relative to `8-9-hh3d-3/`. Existing diagnostic reports are supporting context; the plan remains the sole progress authority. No benchmark/GT06 acceptance follows from this report.
