# S107: bounded preview-cost contrast

AUTHORITY=0. Diagnostic only; never F13/F14, a formal PASS, or public-save performance evidence.

One disposable pinned Godot editor executes 40 native create/undo/save/reload
cycles in ten fixed ABBA groups. A uses the stock `save_scene()` with preview;
B uses `save_scene_as(SCENE, false)` and records its void return as `null`.
The parent owns a 180-second bound including import and child execution. The
original per-phase/heartbeat limits remain intact. There is no HTTP workload,
PSS sampling, injected pressure, discarded warmup, or implicit retry.

The runtime remains source53 `7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`;
profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`
is provenance only: this different diagnostic recipe cannot join its dataset.
`native_probe.py` transforms only exact base
`13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95` in the
generated project. Original source files are checked before/after. Each run
freezes collector, reader, overlay and helper dependencies outside `studio`.

Records bind the owned PID, run, base, recipe, effective source and context.
Call entry/return, signal, phase entry/exit, Engine process frames and next
dispatch remain distinct. The reader permits Engine frames to advance inside
the synchronous call. The first A retains initial scene serialization
normalization; subsequent saved/reloaded scene bytes must match, and script
bytes stay fixed. Semantic create/undo/reload, changed root and generation are
checked independently and bound to native batch/index bytes.

`read_preview.analyze` returns `artifact_status=VALIDATED` only for exact
stdout/report/index artifacts. It reports all 40 observations, distributions
and ten paired group differences. Lifecycle, source/Stop and actual exit checks
are separate in `run_probe.py`; missing metadata stays UNKNOWN. The native
editor should exit naturally at completion. Import wrapper native-handle close
is not supplied by the reused owner API and stays UNKNOWN. A passive outer
observer records the actual Python runner exit; managed Dispose is not a
reported native CloseHandle BOOL. No live Stop exercise is claimed.

Run from `8-9-hh3d-3`:

```powershell
python -B zdoc/reviews/20260919-gt06-s107-preview-cost/run_probe.py --check --run-id gt06-s107-preview-01
```

The coordinator launches once through `s107-coordinator/observe_runner.ps1`
with the exact runner hash. Reusing an existing output ID is rejected. During
execution, keep source/helper/profile/workstation fixed and run no other
engine/test/hash audit. Capture selection explicitly excludes cache/temp and
localappdata; raw failure outputs remain available locally.

Static preparation: 11 native transformation tests, 8 reader tests (including
22 semantic/boundary mutation cases), and 15 collector/ownership tests passed
in one 34-test execution (7.247 seconds, actual command exit 0). These are not
GDScript parser or engine evidence. Three Astra ultra workers delivered native
code, runner code and S106 packet/review work. Supplemental review was interrupted
by a workspace-credit error; no independent final verdict is claimed. The
coordinator integrated the explicit capture allowlist and exact native-batch
bindings, reviewed remaining code and ran the 34 tests.

The source-backed hypothesis is in `../20260919-gt06-s106-latency-next.md`.
Even a clear A/B difference only measures preview cost here, not S102's batch6
latency cause. A nondiscriminating or incomplete result closes this branch;
no larger/repeated experiment or formal workload switch follows automatically.
