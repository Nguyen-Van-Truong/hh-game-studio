# S79: identify editor object owners before another campaign

AUTHORITY=0. GT-06 remains IN_PROGRESS. This is a diagnostic and implementation
review package, not two final critics or an acceptance closure.

S78 full campaign failed at batch 12, with ObjectDB 71124 -> 71128 and no
completed benchmark run. Earlier S77 diagnostic attributed two of four new
objects to TreeItems, but omitted the initial Tree descriptors, so it could
not name the owners. Repeating the same probe would leave that gap unchanged.

The new disposable probe reuses six batches of 100 native semantic cycles and
extends final idle observation to 120 seconds. It adds owner Tree paths,
TreeItem parent IDs and bounded cell text descriptors; the first snapshot
includes Tree and RichTextLabel descriptors. It retains only primitive data.
It still does not enumerate all ObjectDB objects or execute the HTTP mix.
Runtime source, benchmark profile, thresholds and workload acceptance stay
unchanged. No private counter subtraction or minimum-sample selection occurs.

Python and PowerShell syntax were checked. Native parsing and execution are
part of this run; syntax checks alone are not native PASS. The demand-only
attempt 01 was dispatched at 2026-09-18T06:14:01Z but failed before child
creation: outer timeout 720 exceeded the reused runner's 600-second cap.
`attempt01-prelaunch-failure.json` retains that failure; its task was deleted
only after a terminal observation. No native sample or native exit is claimed.
Attempt 02 was dispatched at 2026-09-18T06:15:43Z, but empty TreeItem text
caused the reused HashingContext helper to emit repeated errors and exceed
the bounded log size. Its actual editor exit is absent; wrapper exit 2 is
separate. Outer child exit 1, wrapper 0, verified tree and native Job/handle
cleanup are retained in `attempt02-instrumentation-failure.json`. The task
was deleted only after state 3/result 1/no instances at 06:20:53Z.
The text descriptor now uses String.sha256_text(), including empty strings.
Attempt 03 was dispatched at 2026-09-18T06:23:44Z under its distinct task/output.
Inner/outer/scheduler limits are 540/600/720 seconds.
The scheduler wrapper also records pre-child exceptions explicitly. Lesson:
validate nested runner bounds before increasing a launcher's timeout.
Inspect the live task before describing it as active; after terminal require
actual exits, Job/tree/handle cleanup and all source/helper hashes.

Parallel read-only assignments: object attribution/preflight, derived-index
fault review, and failed-campaign source/cleanup/metric audit. None is an
acceptance critic. Their outputs have separate file scopes.

## Source-supported hypothesis

The pinned engine defines a TextParagraph reference in each TreeItem cell and
instantiates it in the cell constructor. Two new one-column TreeItems could
therefore account for four Objects. This is a source-supported hypothesis,
not attribution of the unenumerated IDs; the new probe must identify the
owning trees and column counts first.

Source: [pinned tree.h](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/tree.h#L59).
Getter API references: [TreeItem](https://docs.godotengine.org/en/stable/classes/class_treeitem.html),
[Tree](https://docs.godotengine.org/en/stable/classes/class_tree.html).

## Journal fault repair

The read-only review reproduced three separate journal ownership/uncertainty
gaps. The coordinator applied the proposed narrow disk-index/service patch
after diagnostic 02 had terminated, and promoted 12 meaningful fault tests.
`index-checks-01` captures an owned 95-test lane, including verified-journal
coverage: 95 pass, no skips/failures/errors; actual target exit 0, wrapper 0,
tree verified, no timeout and 407 source files unchanged. No native backend
is claimed by the fake-backend unit tests. Runtime closure is now 49 files,
`22c30ca840fcd38ec75d919dfd80c6eda3e7965035d8a3e22b0b5246a6152107`.
Earlier source claims remain tied to their old maps. Native service remints,
full benchmark and independent final critics are still required.

Hashing lesson: [pinned HashingContext.update](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/crypto/hashing_context.cpp#L54)
rejects empty input updates; the supported [String.sha256_text](https://docs.godotengine.org/en/stable/classes/class_string.html#class-string-method-sha256-text)
avoids that helper precondition. Instrumentation must pass clean native logs
as well as syntax/API checks before its observations can support diagnosis.

## Completed diagnostic 03

`object-analysis-03.json` was independently reconstructed by the fixed analyzer
with exit 0. It verifies native PID 30616 exit 0, import PID 9416 exit 0,
outer exit 0, Job/handle cleanup, helper/source equality and 25 point hashes.
Six batches of 100 native cycles plus 120.142078 seconds idle retained
71,125 objects at every observation; no new idle TreeItems were seen. This
clean non-reproduction does not establish the cause of the failed campaign.
Its native dependency closure remains `aa58e8ee7fc4f8399766c8d6beca9dfc1bf10b5247ab7f2aba5cb0d40c259b6f`,
separate from the campaign49 and service source domains.

In prior S77 diagnostic03, the first observed focus transition occurs at point
16 (222.27s): focused=false/71123 becomes focused=true/71127; point17 returns
to focused=false while retaining71127. S79 diagnostic03 was focused throughout.
This correlation guides the narrowly scoped synthetic-notification probe in
`focus-probe/`; it is not retrospective proof of the unrecorded event origin.
The probe resolves dialog callbacks and Tree roots in the same process.

After the conversation interruption, the coordinator found no owned HH3D
Python/Godot process still running and no service remint output directory.
The service remint and focus-draft work resumed from existing files; completed
unit and object evidence was not rerun.
