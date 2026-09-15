# S34 solo checkpoint — bounded pipe ownership and effect phase

AUTHORITY=0. The tools plan is the progress authority. This is coordinator
verification, not an independent critic verdict. GT-02 remains CANDIDATE;
safe-write/replace and later consumer mutation remain unavailable.

Frozen run: `GT02-S34-20260916-01`, command `cmd.GT02-S34-20260916-01`.
Source closure: `2d524684563bfff75e77a67a39ac00f1a63f46d5c2cbcd99725c79d2edb12fe7`.
The candidate binds 68 source files and 9 artifacts. Protocol: 194 run, 190
passed, 4 explicit platform skips; bootstrap 56/56. Both suites have actual
host exit 0 and owned process-tree verification. Source and snapshot remain
unchanged. Python/Node/Godot match 2396 golden rows; Godot also rejects 9 cases.

`pipe_io.py` is an internal Windows transport primitive, with 19 real-pipe
tests. Cancellation completion, native close and caller-reference loss are
tested against actual handles and buffers. A pending operation remains strongly
owned and bounded until completion and checked cleanup, including when cancel
reports success or ERROR_NOT_FOUND without a completion witness. Malformed
frames, a short write or failure poison the channel instead of replaying bytes.
Stop is independent of the I/O lock; a frame shares one header/body deadline.
See `studio/host/core/PIPE_IO.md` for ownership preconditions and API sources.

The new tests exposed a separate transport gap at the effect boundary:
`_execute` could write `REJECTED/no_effect` when the guard raised after applying
the fixture, or a setter failed after partially changing state. The fix marks
entry into the effect before mutation. Such failures retain the durable pending
record, close admission, and resolve to `UNKNOWN/RECOVERY_REQUIRED` without
reapplying. Known validation failures before the effect still reject normally.

`reproduce_phase_gap.py` compiles only the old `_execute` method from exact
Git commit `9839be9a77b38199a5c03c86bab5315b9b908955` into its isolated process;
it never swaps a workspace file. The same two regression tests produce four
assertion failures against the old method (three guard-exit codes and one
partial mutation), and zero failures/errors against the corrected method.
`phase-regression.json` records the actual counts and source hashes. Output is
exclusive-create; preserve it rather than overwriting when rerunning a diagnostic.

`verify_evidence.py` rehashes full closure membership, every artifact, actual
child completion markers, host exits, golden rows and requirement-test mappings.
S34-PIPE-IO and S34-EFFECT-PHASE are labels for tested subsets, not new DoD.
`verify_git_bytes.py index` reconstructs exact staged Git blobs and re-runs the
coordinator verifier in a disposable isolated directory, without rerunning
engines. It refuses changed bytes or missing/extra source membership.

The S33 AppContainer diagnostic used its own I/O function and remains frozen.
It is not claimed as native integration evidence for the new pipe module.
Next: actual bound work/control endpoints through session/envelope/journal/
lease/Stop, then immutable release selection with expected generation and
crash/recovery/readback. No new sandbox, activation or two-review acceptance
is inferred from this checkpoint.

The old S33 plan was archived byte-for-byte before trimming the current status
section: `../20260916-plan-history-s33/tools-plan-s33.txt`, SHA-256
`1eb33e360f2c6f712768e453e0bb751e6d539eefb922347614b5e4a613a192f0`.
Historical failed runs, findings, critic verdicts and the earlier blocked S30
TEMP cleanup are preserved. No cleanup retry was performed on that old target.

Source/evidence checkpoint: `abc88b0`. Both index reconstruction before commit
and exact-HEAD reconstruction passed; the second proof is stored as
`git-byte-verification-head.json`. No source change followed the frozen run.

An additional legacy repository-wide governance diagnostic was accidentally
run without a launch-time deadline: `python tests/bootstrap/test_authoritative_plan.py`.
Its `rglob` reads all files, including binary/tool caches outside this tools
scope. It produced no completion marker and was manually stopped after an
observed 207.571 seconds (already beyond the intended 120-second budget).
The target was re-identified by PID 37020, parent 24476, exact command and
creation time `2026-09-15T17:24:38.9409100Z`; a subsequent process query was empty.
The shell's exit 0 after that forced stop is **not** the Python test's exit or
a PASS. This extra diagnostic is not either of the passed frozen candidate
suites. Do not repeat it unbounded or relabel it SKIP/PASS. Future broad checks
must use the existing bounded host runner from launch, if the scope needs one.
