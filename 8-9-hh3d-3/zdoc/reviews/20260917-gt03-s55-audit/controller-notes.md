# S55 single native lane controller

`run_native_lane.py` executes exactly one frozen lane against the shared 176-file
package `../20260917-gt03-s55-source-01/source/studio`, closure
`3a220b51105166274bad4bde950f4cc1d975e87b009b66e52428fad9dc27b02e`.
Controller SHA256:
`46d27dd3a3c188ad90abd8a951d6723314e989ebd642fae6be68dbe1232394da`.

The coordinator must hold the exclusive native/Linux slot before execution.
`--describe` and `--dry-run` start no children. An output must be a nonexistent
direct child of `reviews`; existing evidence is rejected. No runtime is copied.

Example from the repository root (choose a new output and run ID for each run):

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s55-audit/run_native_lane.py --lane save --output 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s55-save-next --run-id GT03-S55-SAVE-NEXT --dry-run
```

Remove `--dry-run` only for the coordinator-scheduled execution.

| Lane | Fixed host deadline | Original crash exit |
| --- | ---: | ---: |
| save | 180 s | — |
| script | 240 s | — |
| edit | 360 s | — |
| stop | 180 s | — |
| fifo | 210 s | — |
| recovery-publication | 240 s | 92 |
| scene-cas | 240 s | 93 |
| script-committed | 240 s | 94 |
| script-retired | 240 s | 96 |
| edit-applied | 240 s | 98 |
| script-unwitnessed | 240 s | 95 |

Each output records its controller copy, invocation, common source reference,
actual raw host exit plus owned Job report, lane result and completion marker,
typed log audit, and post-run full inventory/pin checks. The source manifest,
Windows and Linux executable pins, and controller must remain byte-identical.
A missing raw exit is a failure. Outputs carry `candidate_only=true` and
`gt03_acceptance=false`.

Controller-only verification:

- `controller-inert-verification.json`: 16/16 fabricated metadata checks;
  syntax and save dry-run also passed without an output directory or native child.
- `controller-schema-replay.json`: 90/90 checks against all six completed base
  lanes and five completed cuts. Positive checks read original evidence.
  Negative checks modify only tiny temporary copies, testing raw PID/exit,
  result source hash, missing completion marker, marker count, and original
  crash PID/exit for recovery lanes. Historical source closures are accepted
  only via a test-local constant; the production S55 pin is never changed.
- Historical evidence and the complete shared S55 inventory/manifest were
  unchanged after replay. No native process was started by these validations.

`verify_native_lane_controller.py` contains the replay procedure and refuses
to overwrite its existing report. These checks verify controller behavior and
evidence schemas; they do not substitute for the coordinator's S55 native runs.
