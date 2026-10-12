TICK=no

## Package checked

- Run: `gt10pc-rehearsal-20261012-c3h`
- Frozen source commit: `744a9f61`
- Scheduled-Task studio closure: `86dc9f1cb8fa2e6dc9005d8e4ba2031f4c1862aa930d7287ae9db0077d7724bd`
- Package source closure: `a6280d76c7059d3e1b11aabf6486fe63c00068a19ab8f3c525a569533906da3b`
- Windows 0.1.0 release manifest: `3bb561df55ce31b372447be2a9c7bb9e9a8da4c6655f08db176c266db632b595`
- Trust store SHA-256: `2d19e3e90a719ead39cd1874193f90f98e9f8b2e2b71fb9d0ea451c7336af2e0`
- `git diff --stat 744a9f61 HEAD -- 8-9-hh3d-3/studio`: empty.
- The prescribed `--verify-only` command exited 0 and printed `status=RAW_VERIFIED`, `errors={}`, with no findings.
- Task receipts record returned exit 0 after 1276.484 seconds and an observed process exit. O14 and the current plan honestly call this a rehearsal with one P11 cycle, not a final or soak PASS.

## Findings

### BLOCKER

None.

### MAJOR

1. **P4 negative cases still have no per-case host receipt.** The pre-review required the incompatible-schema and untrusted-rollback refusals on both platforms to have host receipts. The producer invokes both refusal calls in-process (`studio/tests/conformance/gt10pc_p4_negative.py:140-156`), while `verify_negative` only rechecks package/state/exception bytes and never reads a `target_pid`/`exit_code` receipt (`studio/tests/conformance/gt10pc_p4_negative.py:201-270`). Raw case directories contain only command ID, exception, setup where applicable, and before/after state files; no `*-host.json` exists. The whole Windows/Linux producer receipt does not independently bind either negative invocation. This is prereview item 7, reported NOT_FIXED by C4b, and commit `744a9f61` did not modify this verifier.

2. **P11 raw Godot exits are not independently bound by the matrix verifier.** `_verify_p11_short_row` accepts `capture.json.actual_exits` directly and returns them without opening the existing import/editor `process-exit.json` files (`studio/tests/conformance/run_gt10pc_matrix.py:175-205`). The raw receipts currently agree—import PID 37680/exit 0 and editor PID 20620/exit 0—but substituted exit fields in `capture.json` would still verify. The outer Python child receipt (PID 5856/exit 0) does not cure the missing binding for the two Godot processes. This is C4b finding N2 and was not changed by commit `744a9f61`.

### MINOR

None material to this decision.

## Confirmed checks

- P1 archive bytes are rescanned; P2 attack bytes and unchanged ledgers are recomputed.
- P7 verifier checks eight cases, killer/victim/process tree, retry invariance, selector equality, signed release trees, addon bytes, and reasoned NOT_APPLICABLE records. A raw sampled kill receipt matched its cut PID.
- P8 runs all five cases. P9 is a separate child and enforces the P2/P9 known-limit terms.
- P10 binds W02/W03 and L01/L02 host receipts, catalog child host receipts, accepted GT-09 publication/registered/conformance semantics, and both fixtures' seeded 60 Hz pressed/held/released pause/resume traces.
- Source drift is evaluated after raw row validators and yields `DIAGNOSTIC_SOURCE_DRIFT`.

## UNSURE

None.
