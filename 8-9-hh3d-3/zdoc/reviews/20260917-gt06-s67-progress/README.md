# GT-06 S67 progress — acceptance remains open

Checkpoint `843e681` records the authenticated service milestone. This package
adds native adversarial evidence and reviewer implementation verification.
`runs.json` hashes retained raw artifacts; no failed run is promoted to success.

Three actual HTTP/Godot lanes passed on the unchanged 171-file native source
closure `2c623754803e14d59f5d143b3964443a73d21eadaf5947d91fd4a83423e34da2`:

- `gt06-s66-saturated-stop-04`: 15 checks; two real incomplete work connections
  occupy admission while lookup and Stop use reserved listeners. The single
  lookup/Stop observations were 30.4756/3.0307 ms, not p95 measurements.
- `gt06-s66-revoked-result-01`: 18 checks; revoke during running denies the old
  bearer and prevents COMMITTED delivery through the replacement control grant.
- `gt06-s66-stale-capture-01`: 17 checks; after a valid retained capture, changing
  its generated PNG causes a fresh capture request to fail closed. The original
  bytes and mutation witness are preserved in the run's owned directory.

All three have real zero child/wrapper exits and verified owned-tree cleanup.
Forced Stop has no natural-exit object: the driver checks the captured starting
PID and its artifact digest plus the Job's closed/zero state. Completed runs
also require actual natural exit 0. The driver's failed attempt 03 exposed this
distinction; each check is now persisted immediately before continuing.

Reviewer implementation: Tk consumes typed sanitized events, with independent
work/lookup/Stop lanes, keyboard shortcuts, historical inspection, and bounded
owner cleanup. The client keeps credentials private, binds report/native capture
provenance, enforces an absolute HTTP deadline, and never resubmits Play after
response loss. Initial lookup waits for the first POST to finish admission.

The initial `unit-invocation.json` and `unit-capture.json` bind 56 reviewer tests
on their then-current source. The final `reviewer-final-01/` binds **60 reviewer
tests + 6 native benchmark timing tests**, no skips, actual child/wrapper exit0,
unchanged listed source and clean owned tree. These are distinct source versions.

Earlier actual Tk failures remain retained:

- complete-01 exposed initial lookup before admission; source was corrected and
  a concurrent-client regression added.
- complete-02 timed out in its outer owner; no target-exit report was available.
  Missing target PID in that report does not prove the target never started.
- complete-03 failed the bounded native import stage before reviewer creation.
- Earlier adversary attempts 01/02 also hit the 20-second import wall limit.

Read-only environment samples observed CPU 100%, with available RAM ranging
from about 1.6 to 14.6 GiB during this work. This is context, not proof of the
exact timeout cause. No unrelated process was killed and no deadline was raised.
A subsecond unit latency assertion was replaced by causal timer/disconnect/drain
checks; the full benchmark latency thresholds remain unchanged.

Current actual Tk runs **gt06-s67-reviewer-complete-02** and **stop-01** passed:
Ctrl+P launches the prepared Play, completed historical inspection and capture
come through actual HTTP, Esc uses priority Stop, and owned cleanup closes Tk.
Both child/wrapper exits are0 with verified trees. `native-progress.json` binds
their raw artifacts and the preceding failed complete-01; no single latency is
a benchmark percentile. Reviewer closure:
`665320a25e388c97c5e0db9d910a51fdb09edc6eff90a929ffeb536c32ab66d0`.
Replay source closure:
`39d4e8429921f08adef94b3fb4035210e98c2a82676c8d1ba4f965a4ff0f7c41`.
The earlier S66 native adversaries belong to the older closure listed above.

Implementation review caught two UI races: automatic polling could starve
cleanup with slow lookup responses, and a local pre-launch NO_COMMAND could
incorrectly disable Play. Polling now waits for local launch and stops while
closing; late local lookup preserves a newer launch state. Four regressions
cover these cases; generic server READY still cannot enable replay.

The new complete-01 failure preserved an actual tick33 input mismatch: RIGHT
was expected held but the engine reported all keys released. Pinned Windows
code releases pressed input on deactivation; this supports a focus-interference
explanation but the failed run did not record a focus event proving causality.
The fixed authored-trace window starts with `no_focus=true`, checked natively
before execution; reviewer retains the user's keyboard. The new complete/Stop
runs passed without reinjecting held keys or changing the trace. This proves
the fixed trace path, not manual keyboard gameplay in the preview window.
Sources: [Godot no-focus setting](https://docs.godotengine.org/en/4.7/classes/class_projectsettings.html#class-projectsettings-property-display-window-size-no-focus)
and [pinned Windows activation handler](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/windows/display_server_windows.cpp#L6459).

Native benchmark diagnostic02 passed one create/undo/save/reload cycle with
real GUI editor and unchanged frozen bytes, actual exits0 and Jobs closed/zero.
Diagnostic01 reached its complete marker but failed source validation when
Godot normalized the minimal project config. The launcher now prepares exact
pinned canonical config before freeze; project.godot remains hash-protected.
Timing verification additionally requires the save signal between save call
and completion, plus reload observation before the quiescent frame window.
The diagnostic remains one cycle, not the declared full benchmark.

GT-06 still requires the complete declared benchmark, final source/evidence
freeze, affected native remint and two fresh independent critics.
GT-07 through GT-10 remain gated; real Android remains mandatory at GT-08.

Research references checked while diagnosing imports:
[Godot command-line documentation](https://docs.godotengine.org/en/4.7/tutorials/editor/command_line_tutorial.html)
and [upstream import issue 92833](https://github.com/godotengine/godot/issues/92833).
Those reports do not establish that this fixture has the same defect; no engine
flag workaround or accepted-source change was adopted from them.
