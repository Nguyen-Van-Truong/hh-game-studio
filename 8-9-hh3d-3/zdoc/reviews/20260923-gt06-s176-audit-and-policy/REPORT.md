# S176 audit and policy decision

Date: 2026-09-23 (Asia/Saigon)

This review compares the two owner-supplied agent reports with the on-disk
S175 plan, nested AGENTS.md, and current process/Git state. It is a read-only
governance record. `AUTHORITY=0`; it is not GT06 evidence and does not tick a
work package.

## Accepted findings

- Capability and reproducibility checks must precede any new diagnostic. The
  S175 official-symbol boundary already satisfies this rule for the debugger
  path; no S169-S171 retry is justified while the pinned Windows binary still
  has no matching shipped PDB.
- The S172-S174 Godot/Blender slice is useful independent evidence, but it did
  not execute the HH Studio GT03/GT04 command path. It cannot close GT06 or
  prove general game-making capability.
- A real capability catalog is missing for 2D, UI, physics, audio, animation,
  input maps, resources, and physical Android. This is a product-spec gap,
  not permission to weaken a current gate.
- Raw failures and Authority-0 provenance must remain available. A compact
  summary/manifest can be kept in Git; no bulk deletion is authorized.
- Worker capacity failures require bounded attempts and coordinator takeover;
  infinite retries or silent model fallback are prohibited.

## Explicitly not adopted

- The proposed `baseline+64`, `+4/+8`, late-trend, or `2x35` rules are only a
  non-authoritative proposal. The current 10 fresh pairs x 35 batches contract
  and verifier remain unchanged until an owner ADR and fresh critics approve a
  replacement before a new formal run.
- `ATTRIBUTION=UNKNOWN` is not evidence of a leak or root cause and cannot be
  turned into a PASS. It remains the current diagnostic blocker for the
  unresolved ownership path.
- The vertical slice is not renamed as GT06 evidence, and GT07-GT10 are not
  opened by preparation work.

## Next bounded work

Inspect the existing GT03/GT04 command drivers read-only. If one fresh,
bounded consumer pilot can be run through those real paths without changing
the frozen source/profile/gates, give it a new run and command ID and record
source hash, binary paths/hashes, process exits, GLB hash, and postconditions.
Otherwise retain this handoff and wait for owner-provided matching symbols or
another supported attribution integration. Do not repeat a failed branch when
its environment and hypothesis are unchanged.

## Read-only consumer-pilot path audit

The existing `studio/pipeline/run_consumer.py` is an owned GT05 diagnostic:
it calls `run_trusted_stage(consumer.command(...))` directly and binds a GLB,
Godot binary, host capture, and readback. It does not submit a request through
the authenticated GT03 EditorPlugin `/v1/commands` route, nor does the Blender
probe establish a GT04 UI/IPC command-to-asset handoff. Therefore the existing
consumer runner is reusable evidence but is not yet the requested real GT03 /
GT04 consumer pilot. No engine was started while making this determination.

The exact source hashes inspected are recorded in
`consumer-pilot-readiness.json`. A future pilot must add the authenticated
command path and keep the current source/profile pins; the pilot may be
diagnostic only and must not be called GT06 acceptance.

## State

`GT01-GT05=ACCEPTED`; `GT06=IN_PROGRESS/WAITING_EXTERNAL_INPUT`;
`GT07-GT10=PLANNED`; no engine process was running at audit time.
