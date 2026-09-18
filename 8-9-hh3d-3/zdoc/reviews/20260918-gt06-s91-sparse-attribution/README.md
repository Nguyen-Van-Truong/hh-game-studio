# S91: bounded identity attribution and detached exit capture

AUTHORITY=0. Diagnostic only; no GT-06 acceptance or benchmark samples.

S86 grew from 71127 to 71129 Objects before ACK. S90 has already explained
the separate, constant +1 FileAccess lifetime inside ACK; repeating that
35-batch experiment would not answer the remaining question.

The S91 overlay collects primitive TreeItem and Node3D identities at batch 4
before the host baseline sample, then once at the first positive ObjectDB
change in the same phase. It retains no Object references or user text. It
caps identities at 32768 and snapshots at two, and records collection and
publication cost and counter drift. This is a partial inventory: a matching
count is not whole-ObjectDB or leak proof. Native batch/joint/ACK schemas and
the original ACK implementation remain unchanged. The hook consumes the
existing ACK deadline; its timings cannot enter a performance dataset.

The runtime remains the 51-file closure
`e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`
from `b3862a10`; profile remains
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
Only the disposable copied native script receives the helper. Preflight
freezes and verifies the six diagnostic helpers before and after import.

`gt06-s91-sparse-attribution-preflight-01` imported the actual overlay:
native PID 6996 exit 0, wrapper exit 0, natural tree exit, Job zero and closed,
stderr empty. It proves import and closure binding, not runtime attribution.
`preflight-review.md` records the independent implementation readback.

The first controlled smoke (`gt06-s91-sparse-smoke-01`) deliberately remains
failed: its assertion expected +2 Objects for +1 TreeItem and +1 Node3D,
but the actual count was +3. The exact identities were correct and both
collection/publication self-drift checks were false. The pinned Godot
[TreeItem::Cell constructor](https://github.com/godotengine/godot/blob/4.7.2-stable/scene/gui/tree.h#L124)
instantiates a TextParagraph. A one-column TreeItem therefore creates two
Objects. This explains the smoke assertion; it is only a hypothesis for S86
until the real workload identities are captured. Raw source, output and
actual native exit 1 remain preserved under the smoke run ID.

The corrected `gt06-s91-sparse-smoke-02` ran two controlled cases in one
native process. A single TreeItem produced ObjectDB +2 / targeted IDs +1;
TreeItem plus Node3D produced +3 / +2. Both arms passed all 22 checks,
including no counter self-drift, two-snapshot cap, exact IDs and integer JSON
serialization beyond 2^53. Actual native PID 55068 exited 0, wrapper exited 0,
Job zero/closed, stderr empty. Capture SHA256:
`ecad22411f3c9bab328a12ea03e09f74f05ec6df6c5fbcae8bbf77fe9bc34ab5`.
This validates the unchanged helper on known additions, not S86 attribution.

The demand-only Windows task runs `launch_observer.py` through pythonw. The
observer retains native supervisor, helper, host and editor handles outside
their inner Jobs. A gated child starts only after checked outer Job adoption.
The outer limit is seven processes; original inner limits are unchanged.
Natural and forced exits are distinguished. Three Python-only tests checked
natural exit 0, forced exit 2, Job zero/close and handle release. Scheduler
terminal state is still required for the observer's own completion; scheduler
success alone never proves the diagnostic passed. Power loss or an externally
killed observer can still leave evidence missing.

One long diagnostic may run after the controlled smoke and preflight have
passed. Its wall limit is 7410 seconds; the observer has 7530 seconds and the
scheduler 130 minutes. No retry, periodic task trigger, counter allowance,
baseline adjustment, priority increase, working-set trim or mutation of
unrelated processes is permitted. Keep source/helper/profile fixed while it
runs. Inspect live task state and a short log tail before declaring it alive.

From repository root, after readiness checks:

```powershell
& 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s91-sparse-attribution/register_task.ps1 -Command register
& 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s91-sparse-attribution/register_task.ps1 -Command status
```

The task is `\HHStudio.GT06.gt06-s91-sparse-attribution-01`; launch and observer
receipts live in this directory's `launch/`. Raw diagnostic data live under
`studio/.local/reviews/gt06-s91-sparse-attribution-01`. Do not launch the long
supervisor through an exec PTY. Preserve a failure and diagnose it before
another attempt; completed raw data can support repaired offline metadata
without rerunning the engine.
