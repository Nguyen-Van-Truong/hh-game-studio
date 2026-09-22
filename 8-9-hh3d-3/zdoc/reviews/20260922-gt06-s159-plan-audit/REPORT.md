# GT06 S159 plan audit (read-only)

- **Audit ID:** `GT06-S159-PLAN-AUDIT`
- **Audit time:** 2026-09-22 (Asia/Saigon)
- **Scope:** `8-9-hh3d-3/zdoc/8-9-godot-blender-agent-studio-plan.txt` and every nested `AGENTS.md` under `8-9-hh3d-3`.
- **Mode:** static/read-only. No Godot, Blender, benchmark, worker, or agent was started. No plan checkbox, ACCEPT state, source, or benchmark was changed.

## Snapshot and provenance

- Repository `HEAD`: `77b4362a9b97348137bae8c31512a2a15fbb10fc`.
- Tracked diff for the plan and scoped `AGENTS.md`: exit `0` (`git diff --quiet -- <paths>`).
- Plan SHA-256: `51B351B1E0C3C753788A97A27FEB610E3D1EAF3475E36A4D6A16914AA1979117`.
- Root `AGENTS.md` SHA-256: `DFE8D35C49275C89DCA4EBA27A44651FD5299F31EF0928AA613AB07300547350`.
- Scoped `8-9-hh3d-3/AGENTS.md` SHA-256: `2FBB4A617CA036A602AD42490C69701F4014E5C1A343D4C3A79F8A195970281F`.
- Nested snapshot instructions were found under `studio/.local/`; they are historical artifact instructions and explicitly defer to the plan's first table/CURRENT_VALID_WP.

S158 coordinator review (`zdoc/reviews/20260922-gt06-s158-coordinator/s158-coordinator-review.json`, SHA-256 `2A242A4A02D9D72DCC55E5484B91E984AE8710BC5258AE4814744D245DACAE3F`) records `authority=0`, `formal_acceptance=false`, `eligible_for_dataset=false`, `cursor_lanes_terminal=true`, `astra_lanes_requested=3`, `astra_lanes_started=0`, and `astra_capacity_errors=3`. Its decision is `HOLD_NO_ENGINE`; the process probe reports no matching engine/helper process.

The bounded S158 static checks are useful diagnostics only:

- hardened-contract tests: 3 tests, exit `0`, output SHA-256 `29e718fb17660bd2975cba4a1b410145fc1877e5d2513a410b198157d6f3cbaa`;
- hardening-guard tests: 2 tests, exit `0`, output SHA-256 `899dd2fd4852951cc9619887cc0bc8cddd38d7d11b4e4c031b3e6eafb6c2acab`;
- S158 contract-exit artifact SHA-256 `D06A2BC5633E483D65E5B4B727F54C9425B0D19B5623EF26FC8E71BA66804D25`;
- S158 hardening-exit artifact SHA-256 `0612BDF335A9B78247D58AE806ECFABFC4A89F1D8A78605ABFBF7E26856CDCA2`;
- process-probe artifact SHA-256 `90CD0B3DF3BA9F4A749AA38419B6594BDB69AF493B427A339F4E83FCE88A9887`.

## Findings

### S158 status is internally safe but not acceptance

The plan's first table keeps `GT-06 | IN_PROGRESS` and `CURRENT_VALID_WP=GT-06`. The top metadata correctly preserves zero accepted full runs, the S141/S147/S153/S156 failures, `AUTHORITY=0`, the three Astra capacity refusals, and the ban on engine dispatch until a distinguishing contract is reviewed. This agrees with scoped `AGENTS.md` S158 routing: Cursor is terminal; Astra was requested but none started; coordinator owns static review.

The S158 hardening review blocks the next diagnostic until helper bytes, contiguous original-gate prefix, target PID, and documented PSS fields are strictly bound. The reserved PSS fields are not valid temporal attribution. This is a diagnostic gate, not a GT06 PASS or no-leak/root-cause result.

### GT06 DoD remains open

The GT06 DoD at plan lines 1056–1079 requires `TQ06/TX02/05/13` and two independent critics. TQ06 requires a real menu-to-play-to-move-to-interact-to-pause/resume/quit trace at 60 Hz with pressed/held/released/seed, post-transition readback, frozen simulation tick with responsive UI clock, seeded fault before/after, and schema-validated perf output. TX02/TX05/TX13 additionally require stable target/revision handling, owned PID/start-time cleanup with actual exits/leftovers, immutable runtime snapshot and separate editor/play roles, and no stale capture.

S158 only proves fake/static contract and eligibility guards. The plan itself says `ZERO_ACCEPTED_FULL_RUNS`, and the next-action metadata still requires a fresh `10x35` campaign, final evidence, and two new same-hash critics. Therefore GT06 cannot be promoted, ticked, or used to open GT07 from this snapshot.

### Cursor/Astra wording needing compaction

1. The live top metadata says `EXECUTION_MODE=...ASTRA_XHIGH_REVIEW_WORKERS...` and `SUBAGENTS_ENABLED=CODEX_GPT_6_ASTRA_XHIGH ... GOAL_ACTIVE`, which can be read as active workers. S158 evidence says `requested=3`, `started=0`, `capacity_errors=3`, and static-only coordinator takeover. This is a stale/ambiguous active-state label.
2. Plan section 8.2 line 1450 still says “Owner steering mới nhất 17-09-2026: ba Codex subagent Astra extra high...”. It is older than S158 (22-09-2026) and should be explicitly marked historical or replaced by a current dispatch-state line.
3. The plan retains many S157 historical paragraphs naming Cursor/Grok and old worker models (for example lines 76–219 and the S157 handoff text). They are valid provenance only because the surrounding text labels S157/history; they must not be interpreted as current dispatch instructions. The nested `.local` snapshot `AGENTS.md` files similarly contain 14–17 September Cursor/Grok/Astra policies and are evidence snapshots, not current routing.
4. `GT06_WORKING_SOURCE_STATUS` still describes the S145 candidate/S147 terminal failure while the top current closure is S156 (`fce149cd…5ddcde`). This is not an acceptance error, but it is a compact-metadata ambiguity that makes the active diagnostic closure harder to identify.

## Proposed compact metadata (proposal only; not applied)

Place one authoritative S159 block immediately after the first table and keep detailed S157/S158 prose as history:

```text
PLAN_REVISION=S159
CURRENT_VALID_WP=GT-06
GT06_STATE=IN_PROGRESS; AUTHORITY=0; FORMAL_ACCEPTANCE=false
GT06_DOD=TQ06+TX02+TX05+TX13+2_CRITICS; STATUS=OPEN
DISPATCH_STATE=COORDINATOR_STATIC_REVIEW_ONLY
CURSOR_STATE=TERMINAL_RETAINED; ACTIVE=0
ASTRA_REQUESTED=3; ASTRA_STARTED=0; ASTRA_CAPACITY_BLOCKED=3
ENGINE_EXECUTION=FORBIDDEN_UNTIL_S159_CONTRACT_REVIEWED
CURRENT_SOURCE_CLOSURE=fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde
CURRENT_EXECUTION_CLOSURE=78ffef60682f596313aac8aca69a06e0a23808c546202effdebc481bdb845b58
NEXT_ACTION=review_fresh_helper_contract; then_one_bounded_diagnostic_only
```

Mark section 8.2 as `HISTORICAL_POLICY_AS_OF=2026-09-17` or remove the dated worker sentence. Keep the S157/S158 paragraphs for provenance, but prefix each dispatch block with `HISTORY_ONLY=1`. Do not change the GT06 DoD, gate rules, source pins, evidence, or plan checkbox in this audit.

## Limitations and disposition

- No engine or benchmark was run by this audit, so runtime behavior, actual target exit, leak status, and gameplay/readback claims remain unverified here.
- This report does not validate the proposed fresh helper; S158 explicitly requires coordinator contract review before any diagnostic.
- No independent critic signature was created. `TICK`/`ACCEPT` remains **not granted**.
- Audit command set was read-only inventory/hash/diff inspection; command exit was `0` for the scoped diff check. The report itself is the only new file in this lane.

**Disposition:** `REVISE_METADATA_ONLY`; retain GT06 `IN_PROGRESS`, `AUTHORITY=0`, and the S158 no-engine hold.
