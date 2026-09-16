# GT-03 S54 recovery crash-cut component result

**Five distinct native crash classes completed: 108 functional checks.**
Component evidence only; no GT-03 acceptance or independent critic signature.
No production source, plan or commit was changed by this cut/audit lane.

Frozen runtime source closure:
`478797d092509af2ae88cf3ad7a71b28b09a55e401d4b51e90c91544c0319564`.
The complete source snapshot is in
`../20260917-gt03-s54-recovery-cuts-02/source/studio/`.
All source bytes were rechecked by the read-only completion audits.

| Actual cut | Package / case | Checks | Publisher exit | Case exit / wrapper | Result |
|---|---|---:|---:|---|---|
| Scene selector CAS before durable SELECTED | cuts-02 / scene-cas | 21 | 93 | 0 / 0 | Functional PASS; separately audited log classification |
| Script COMMITTED before returning response | cuts-03 / script-committed | 21 | 94 | 0 / 0 | PASS |
| Script old-editor retirement before selector CAS | cuts-03 / script-retired | 21 | 96 | 0 / 0 | PASS |
| Actual editor update after EDIT_READY, before EDIT_COMMITTED | cuts-03 / edit-applied | 21 | 98 | 0 / 0 | PASS |
| Script native COMMITTED before custody witness | cuts-03 / script-unwitnessed | 24 | 95 | 0 / 0 | PASS |

Here `cuts-02` means `../20260917-gt03-s54-recovery-cuts-02/` and `cuts-03`
means `../20260917-gt03-s54-recovery-cuts-03/`. Every case has its raw
`recovery-cut-host.json`, `original/publisher-host.json`, saved wrapper
reports, `result.json`, fresh editor readback, response wire bytes,
recovery event export and `editor-close.json`. All owned case/publisher
process trees were verified empty. Fresh recovery editors exited 0 with
closed Jobs, active count 0, and no retained owner handles. The existing
cuts-03 runner (PID 3056) completed naturally with observed outer exit 0;
it was not replaced or relaunched after the agent interruption. Final CIM
inspection found no cut-run Python or Godot process.

## What the checks establish

- Actual HTTP publication/edit effects and actual engine/Linux validation
  precede each cut; these are not synthetic storage receipts.
- Recovery obtains a fresh higher fence and editor generation, checks exact
  expected scene/script semantics and all 11 selected file bytes, and keeps
  selected protected files read-only.
- A witnessed COMMITTED command replays the exact original response bytes,
  including fresh-host retry after readback and reopen.
- Retired-before-CAS and applied-but-uncommitted edit cases return explicit
  recovered REJECTED results and restore the selected last-good project;
  volatile editor history is not claimed restored.
- The unwitnessed native commit remains blocked as an original ACK. Fresh
  reconciliation writes a distinct durable recovered response with explicit
  original-outcome uncertainty; lookup/retry/reopen replay those exact bytes.
- The denied lookup-only grant is tested before minting the final recovery
  lease. The actual recovery request remains capped at 29 seconds, within
  the unchanged 30-second runtime contract. Publication preparation retains
  29-second edits, 89-second saves and a fresh 90-second lease after dirty edit.

## Evidence qualification and preserved failures

`cuts-02/capture.json` remains **false**, exactly as originally generated.
Its case passed all 21 functional checks and raw exits, but the broad log
regex treated Docker's empty `State.Error` JSON field and the expected
post-removal absence probe as errors. `scene-cas-completion-audit.json`
independently passes seven checks and binds those known records to exact
owned container IDs, successful removal output, expected inspect exit 1,
empty inspect result and clean native Jobs. It does not overwrite the raw
capture or ignore arbitrary error text. `log-scanner-source.py` freezes that
read-only classification code.

`cuts-03/capture.json` is **PASS** for all four cases. It reuses the exact
cuts-02 runtime snapshot and records a separately frozen driver:
`d2fd6a89119cd59d0c8e92efe2ac6c1d143df4f2f8e1f8e255f74905a3036fd2`.
`runtime-source-reference.json` records that composition; it is not a claim
that the newer scanner belonged to the old runtime closure.
`matrix-completion-audit.json` independently verifies the case inventory,
raw exit/PID bindings, source/driver bytes, functional results, editor
cleanup and typed logs. Audit reproduction is file-only:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s54-recovery-cuts-audit/audit_scene_completion.py
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s54-recovery-cuts-audit/audit_matrix_completion.py
```

The older `c354c978...` runtime package and recovery-only resumes 01/02 remain
preserved failures. Their real publisher exit 93 did not make the missing
original outer exit a pass. Both continuations hit deadline before commit
and durably held recovery; the second failed without competing native unit
load. Timing reports and the atomic-inspection code review explain the
coordinator's runtime repair and its exact-owner guard correction. Old
failures were not relabelled as proof for the new runtime.

## Remaining limits

`script-cas`, `scene-committed` and `edit-ready` are defined but were not run;
no individual coverage claim is made for them. The earlier capture-before-
CAPTURED recovery package belongs to its own source closure. This scoped
matrix does not establish every Stop/revocation boundary, a full final
integration suite, or two independent acceptance reviews on the final
coordinator closure. The root schedules later integration separately.

The lane changed only the recovery test harness and audit/evidence files.
All completed case evidence and failures remain intact; no worker commit
or plan tick was made.
