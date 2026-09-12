# S21 plan audit (read-only)

**Scope.** Audit of the two canonical S21 plans at review base `b4195ca`, plus the
`20260912-r10` candidate evidence. This is a design/evidence audit; it does not
accept or tick any work package.

## Findings

### P0 — GT-01 DoD has a cross-WP acceptance cycle

The GT-01 DoD requires `TQ01/TX12/TX14` and two critics (tools plan §3,
lines 367–393). Yet TX12 explicitly assigns ABI/build verification to GT-08 and
installer/migration/rollback/uninstall acceptance to GT-10 (lines 679–684), while
TX14 assigns substantive journal/token/stop/recovery behavior to GT-02, GT-07 and
GT-10 (lines 689–693). GT-01 is therefore unable to become `ACCEPTED` without
later WPs that depend on GT-01; this is a real acceptance dependency cycle even
though the summary DAG lists GT-02→GT-10 linearly.

**Correction/acceptance criterion:** split the GT-01 gate into (a) a bounded
candidate smoke subset owned by GT-01 (cache isolation, no destructive upgrade,
stop-before-reconnect and evidence capture), and (b) explicit deferred TX12/TX14
rows owned by GT-08/GT-10. The GT-01 DoD must name only tests executable with
GT-01 artifacts and must state that deferred rows remain blocking for their own
WPs, not GT-01. A static dependency checker should report an acyclic owner graph.

### P1 — `GT01_PENDING` is accurate but underspecified for the new candidates

The summary correctly keeps `GT01_EVIDENCE_STATUS=PARTIAL_RUNTIME_UNREVIEWED` and
lists source freeze, archive verifier, installer recovery, runner admission,
official runtime, TX12/TX14, and two critics as pending (lines 17–25). This remains
accurate: `runtime-candidate-5` has a real Godot exit 0 and verified process tree,
but its manifest still says candidate evidence requires archive verification and
independent critics; candidate-1/2/3 include admission exit 2 (`GT01_GAP: output
must be new and outside studio root`). The candidate's `source_manifest_before`
and `after` are useful but do not constitute an owner-signed freeze/archive
verifier result.

**Correction/acceptance criterion:** replace the free-form pending list with a
machine-checkable matrix containing artifact path, run/command ID, source hash,
owner, and pass/fail evidence URI. Mark each item complete only from independently
parsed evidence (host exit/wait result, archive verifier output, installer
rollback/recovery result, and critic signatures on the identical frozen hash).

### P1 — Candidate evidence claims need a single authoritative selection rule

Three candidate directories coexist under `20260912-r10`; one is a known GAP,
one diagnostic, and candidate-5 is a passing runtime smoke. Without a declared
selection rule, a packer or reviewer could accidentally combine logs/manifests
from different source hashes or runs. The tools plan requires source/runtime
hash binding and fail-closed evidence (§2.5 and GT-01 VERIFY), but the S21 summary
does not identify which candidate is authoritative.

**Correction/acceptance criterion:** require exactly one candidate manifest per
source freeze, reject mixed run IDs/source hashes, and record superseded
candidate directories as non-authoritative. The selected package must include
the archive/install verifier outputs and critic records in the same immutable
evidence directory.

### P1 — Game plan dispatch gate is coherent, but wording should distinguish tool
acceptance from tool implementation progress

The game plan correctly sets `CURRENT_VALID_WP=H2-P0-01`,
`DISPATCHABLE=NO_UNTIL_GT10_ACCEPTED`, and `IMPLEMENTATION=NOT_STARTED` (lines
39–45), while the tools plan remains GT-01 in progress. This is internally
consistent and prevents premature game work. However, the consumer contract says
GT-10 must be accepted before H2-P0-01 (world plan §0 and lines 6–11), so any
future evidence mentioning a “working” tool must not be interpreted as a game
dispatch authorization.

**Acceptance criterion:** retain the gate and add an explicit checker assertion
that no H2 WP can transition out of `PLANNED` until a GT-10 manifest, trust-key
verification, and rollback-compatible package are present.

## Non-findings

No additional contradiction was found in the S21 game WP ordering itself. The
plans consistently state that gameplay does not wait on a hypothetical engine
fork and that map/Hoàn Hảo integration follows authored gameplay. No runtime,
legal, or human acceptance is claimed by either plan.
