# S79 focused causal probe — draft, native run pending

Reviewed against HEAD `24efe96757a7b0a25c4a11471152fd1911d764f0`.
No engine was launched for this review. Seven no-engine Python checks pass;
GDScript parsing and all native postconditions remain unverified until execution.
This is a bounded disposable diagnostic, never GT06 or benchmark acceptance.

After the coordinator has released the serialized engine lease, run once from
the repository root with ordinary, non-optimized Python:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s79-diagnosis/focus-probe/diagnose_focus.py
```

The fixed run is `gt06-s79-focus-diagnostic-01`. Existing output causes failure;
do not delete or overwrite it to retry. The outer receipt goes to
`focus-owner-01/` beside the helper. Native evidence goes to
`studio/.local/reviews/gt06-s79-focus-diagnostic-01/`. Copied helper files in the
receipt directory are retained source, not alternate runnable entry points.

The entry point resolves HH3D root from its original location, imports the
benchmark owner and fixture dependencies before freezing source, copies the
trusted fixture, and instruments only its disposable benchmark plugin before
import. Import has no benchmark activation argument. GUI launch explicitly opens
`res://scenes/fixture.tscn` and passes `--hh-benchmark-mode=diagnostic` after `--`.
The accepted adapter, runtime source, object03 helpers, and benchmark thresholds
are unchanged. Both helpers are hashed before/after the owned child.

Limits: unchanged 20s import cap; 150s host watchdog covering import and editor;
180s outer owned cap, below the runner's 600s maximum. The editor's unchanged
Job profile still declares 7410s wall/7200s CPU/2GiB/4 processes; it is not
misrepresented as a 150s Job limit. Focus observations have a separate 30s
deadline, six points, two stimuli, 64 events, 64 items per Tree, 50,000 scanned
nodes, depth 128, and byte caps. Host exits, zero descendants, closed Job/handles,
unchanged source, and clean native logs must verify before diagnostic completion.

One native create/undo/save/reload cycle precedes the baseline. The six points
are: baseline; settled pre-stimulus; immediate return from first stimulus;
settled/pre-second; immediate return from second; settled final. Each settle
requires both 1.5 seconds and eight process frames. Each stimulus is explicitly
**SYNTHETIC** `SceneTree.root.propagate_notification(APPLICATION_FOCUS_IN)`;
it neither changes OS focus nor proves an OS focus event occurred. Events outside
the dispatch are labeled only as received outside the probe. No private callback
is invoked and no `Tree.clear()` is called by the probe.

Live `confirmed` callback target class/method identifies EditorNode's scene-change
dialog and ScriptEditor's script-change dialog. Every point retains same-PID
dialog/Tree IDs, title, visibility, root/null and child text, counters before/after
collection, prior-root validity, window title/focus, and scene/source file hashes,
sizes and modification times. The verifier requires stable owner identity,
callback/title/file state and checks the actual saved scene against the native
cycle. Counter equality during collection is recorded honestly, not imposed;
root allocation/replacement/non-reproduction is also retained without forcing
the hypothesis to pass. No ObjectID is joined across processes.

Interpretation: a missing root becoming present can test retained initialization;
later changed root IDs with invalidated prior IDs can test replacement. Already
initialized roots may show replacement with no net growth. Two observed roots do
not identify the two private TextParagraph objects. `root_cause_proven=false`
remains explicit, including after a clean diagnostic. S77/S78 causation and full
benchmark acceptance require separate evidence.

No-engine check:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s79-diagnosis/focus-probe/test_probe.py
```

Possible startup-readiness repairs, for coordinator review only: if this probe
confirms lazy blank-root creation, establish that the pinned editor's actual
startup/focus handling has completed before choosing a measured baseline, with
same-process callback/root evidence. Main-window `has_focus` alone is inadequate.
A bounded public synthetic notification during explicit startup is another
candidate, but must be disclosed, given its own postconditions, and uniformly
included in a newly frozen/reminted profile; this diagnostic does not silently
adopt it. Never clear private Trees, subtract four objects, relax the object-count
gate, or infer readiness from IDs seen in a different process. If the adapter's
initial scene is unbound, retain the existing bounded readiness wait and require
the approved scene/root/generation to settle; do not reinterpret permanent wrong
scene/held state as ready. No runtime readiness repair is applied here.
