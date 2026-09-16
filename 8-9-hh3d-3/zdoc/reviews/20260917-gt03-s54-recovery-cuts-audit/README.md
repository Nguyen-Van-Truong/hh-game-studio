# GT-03 S54 crash-cut continuation audit

Implementation evidence only. No independent acceptance review and no tick.

Current completed component result: see [component-summary.md](component-summary.md).
Five distinct native cuts total 108 functional checks on runtime closure
`478797d092509af2ae88cf3ad7a71b28b09a55e401d4b51e90c91544c0319564`.
`scene-cas-completion-audit.json` and `matrix-completion-audit.json` pass;
the former preserves cuts-02's original aggregate log-classification false.
All native case/publisher exits and owned cleanup were captured. The older
failure history below remains unchanged in its original packages.

The interrupted `20260917-gt03-s54-recovery-cuts-01` package has runtime
closure `c354c978062dc9987f98eae28d5af158bed5256ba25126457be44d43a720150f`.
Its scene-CAS publisher completed the actual authenticated dirty edit,
isolated Linux validation and native selector CAS, then exited at the
intended fault hook with raw target exit **93**, wrapper exit **0** and
verified empty owned process tree. `SELECTED` was still absent and the
original command phase was `ACTIVATING`. The outer recovery process was
interrupted and has no raw exit or final result; that package is incomplete.
No `script-committed` case ran in that interrupted package.

`20260917-gt03-s54-recovery-cuts-resume-01` retains the original publisher
evidence and storage ID, verifies its raw PID/exit against the saved wrapper
report, and uses the exact unchanged frozen runtime. A separately frozen
`driver.py` has hash
`5a9e91df46a76841e9bf060d4cba7a93ecc55dd16aa320446a8d87c9a814901b`.
The continuation is explicit composite evidence, not a replacement exit for
the interrupted original. Source files remain in the original package and
are referenced by `runtime-source-reference.json`; they were not rewritten.

The first continuation **failed**. It preserved the selected candidate,
blocked the unfinished original ACK, obtained a higher fence, denied a
lookup-only grant, and started a fresh editor. The commit-phase live
authority check then raised `GODOT_DEADLINE_EXPIRED`. HTTP returned
`UNKNOWN`, `public_ack=false`; no recovered terminal was claimed. The
continuation target exited **2**, wrapper **0**, with a verified empty owned
tree. The recovery editor exited **0**, wrapper **0**, Job active count **0**,
without warning/error output. The failing diagnostic traceback is retained.

`timing-report.json` and `timing_audit.py` record a read-only artifact audit:
request-write to editor spawn **20.796 s**, spawn to hello **5.244 s**, and
only **2.959 s** remained before the unchanged request deadline. The root's
native storage/Registry tests overlapped this attempt. Overlap does not prove
causation; a quiet authorized continuation is needed to distinguish disk
contention from journal-length and repeated-readback costs. The older
successful recovery has a different closure and shorter original journal.

After that disk load stopped, the coordinator authorized one quiet
continuation in `20260917-gt03-s54-recovery-cuts-resume-02`, again using the
same frozen runtime, original publisher and storage ID with a 29-second
request. It also **failed** with `GODOT_DEADLINE_EXPIRED`, this time during
commit `reserve_phase` after the pre-phase native context check. The HTTP
result remained `UNKNOWN`, `public_ack=false`; the two durable recovery
attempts are both `HELD` and neither is `TERMINAL`.

`quiet-timing-report.json` records request-to-spawn **18.341 s**, startup
**3.851 s**, **6.807 s** left at hello and **34.722 s** request-to-UNKNOWN.
The quiet case target exited **2**, wrapper **0**, empty owned tree; the
editor exited **0**, wrapper **0**, Job active count **0**, clean engine
logs. The harness now also preserved the failure journal snapshot and raw
recovery event export. The runtime/selected content remained unchanged;
the same storage necessarily includes the previous failed recovery suffix.
This failure shows that concurrent test load alone does not explain the
route's budget problem. Further fresh publishers are paused for the runtime
owner to address it without weakening deadlines.

`recovery-read-graph.md` maps 13 complete native replay/validation passes
before editor startup and 36 through the ordinary host terminal response,
plus 13 required native content durability barriers. It proposes a
journal-owned atomic inspected view to consolidate repeat reads within one
logical observation, retaining every fresh effect boundary and post-append
check. No runtime change was made in this lane.

Pending bounded cases are script terminal-before-return,
script-retired-before-CAS, edit-applied-before-commit and script terminal
before custody witness. Unexecuted adjacent cases remain unclaimed.

Harness changes are confined to `studio/tests/godot/run_recovery_cut_matrix.py`:
existing frozen runtime reference, separate driver hash, recovery-only
resume, exact original raw exit cross-check, existing terminal detection,
failure snapshot preservation and complete stdout/stderr scanning. The
existing-terminal branch captures exact lookup without a new engine or
append, then reports that prior readback artifacts need audit rather than
manufacturing a complete pass. No runtime or plan files were changed.
