# Independent plan audit — 2026-09-11

## Scope and result

Audited the two canonical plans at revision S18, the S18 review report, toolchain lock and partial GT-01 evidence. This is a design audit, not runtime, legal, human, or capacity acceptance.

- Tools plan: `8-9-godot-blender-agent-studio-plan.txt` — `CURRENT_VALID_WP=GT-01`, `IN_PROGRESS`.
- Game plan: `8-9-hh-world-gameplay-viet-nam-plan.txt` — `CURRENT_VALID_WP=H2-P0-01`, dispatch blocked until GT-10 is accepted.
- Static validator: `PASS_STATIC_ONLY`; S18 mutation suite: 31/31; GT-01 static tests: PASS; runner contract tests: 5/5.
- Partial runtime package `20260910T131143Z`: 9 expected subprocess outcomes, including Blender overwrite rejection; explicitly not GT-01 acceptance.

## Strengths confirmed

The plans have a clear one-way dependency graph, one source-of-progress table per plan, explicit ownership/allowed files, immutable source hashes, fail-closed evidence language, process ownership and cleanup requirements, idempotency/UNKNOWN semantics, path and reparse-point protections, staged publish/rollback, deterministic input traces, real-input versus synthetic evidence labels, privacy/retention and deletion handling, DB durability fault models, geo licensing gates, accessibility targets, overload/cost controls, and explicit limits on 100M-account/CCU claims. S18 also records that earlier leader/hold and Solo-cap ambiguities are resolved in the current wording.

## Remaining design gaps to close before public release

1. **P1 — payment boundary is implicit.** P4-02 deliberately excludes real-money payments, but the release gate does not name a hard `monetization=OFF` invariant or a future payment work package. If any store/platform payment, voucher, refund, chargeback, tax, parental approval, or regional price is introduced, add a separate owner/WP and test receipts, reconciliation, entitlement revocation, refund/chargeback, and provider outage. Until then, assert the shipped artifact contains no payment SDK, purchase endpoint, or monetization UI.
2. **P1 — key-management and CDN/object-store disaster path needs an explicit drill.** DB-D3 and release sections cover DB/WAL/PITR and key rotation, but public readiness should also require restore of signed manifests/content from an unavailable primary object store/CDN, KMS/key loss or rotation, CDN corruption, and client cache eviction. Prove last-good package admission, rollback, and bounded user messaging without serving unsigned content.
3. **P1 — privacy/telemetry proof is still a future gate.** The design names purpose, retention, residency, deletion and redaction, but P3-01/P6-02 must produce a field-level inventory for crash reports, input traces, screenshots/video, IP/device data, moderation evidence and support exports. Test deletion/hold/backup replay and access controls across every copy and region; prove no raw token, chat, precise location, or child data enters telemetry.
4. **P2 — accessibility acceptance needs measurable platform coverage.** The plan names 200% text, labels, focus order, reduced motion and assistive technology, but P5-02 should enumerate supported Android/Windows accessibility stacks, minimum contrast/target sizes, keyboard/touch remapping, screen-reader announcements for async UNKNOWN/PENDING states, and a human test matrix. Missing OS capability should produce a documented fallback/GAP.
5. **P2 — operational ownership should be machine-checkable.** Every P6/P8 alert and runbook should include an on-call role, escalation SLA, notification channel, cost owner and drill date. A dashboard without an owner or a synthetic-only drill must fail the gate.
6. **P2 — release claim guard.** Add a release-manifest assertion that published capacity is the last measured cap (`r_node`, room cap, region and workload profile), and that marketing/store metadata cannot state 100M accounts, 100M CCU, or seamless world behavior without a new signed capacity/legal decision.

## Repository hygiene finding

The current checkout intentionally contains two deleted historical plan paths, many untracked historical review artifacts, and modified older validators alongside the committed S18 checkpoint. Before the next implementation WP, create a clean checkpoint or explicitly quarantine these files; otherwise an accidental broad commit can mix historical evidence with canonical source. Do not delete evidence merely to make status clean.

## Decision

`DESIGN=STRONG_BUT_NOT_PUBLIC_READY`.
`GT01=IN_PROGRESS`; no plan checkbox should be ticked. The canonical S18 plans are internally coherent and substantially better than the superseded plans, but they are not “final/best proven” until the listed gates have owners, executable evidence and independent critic approval.
