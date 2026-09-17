# S76: cadence fix and attributed diagnostics — not GT06 acceptance

The full S75 campaign failed. `failure/README.md` preserves 264 raw files,
162 exact copies and the failure seal
`c32c448713aed56f48c73c79ae68613903b41e9fabf36fb8a69ef1852c21e6e9`.
Editor handles increased577→579 at batch8 and an HTTP status gap was2016.2214ms.
Neither failure is waived. No complete campaign run exists.

## What changed

The benchmark fixture now pins both focused and unfocused editor sleep to6900µs
before import. Continuous updates remain false and the Output display limit100.
An early native guard checks exact configured keys, types and effective settings;
the native readback is bound to run/PID/source/profile. Accepted authoring adapters,
command mix, warmups, quiescence, thresholds, deadline and profile are unchanged.

`current-runtime-source.json` binds49 full-campaign dependencies, closure
`ffa6071a1fb9d324da7cd860fb41b656e99135a3118367873c7399e85e8432fe`.
Only `tests/replay/run_native_benchmark.py` and `benchmark_native.gd` changed in
that map; three configuration regression tests were added separately.
Load the declared fixture before collecting dynamic imports: otherwise three
fixture modules are missing. A diagnostic's smaller map is not this49-file map.

`cadence-units-01/`:57/57 targeted unit tests, actual target/wrapper exit0 and
owned tree clean. `cadence-native-owner-01/` and `cadence-readback.json` bind the
fresh one-cycle positive native run. Actual editor24908 exit0, clean Jobs;
native effective sleep6900, exact settings and save/undo/reload readback verified.
Its diagnostic map has38 files; do not relabel it as the full campaign closure.

## Cadence and handle observations

`diagnose_handles.py` copies a disposable fixture and runs6×50 cycles, then60s
idle. It publishes a closed temporary point file before PSS, retaining PID,
creation time and executable identity. PSS requests handle metadata only, not
memory/thread-context clones. Kernel names are hashes; unknown types stay unknown.
`compare_handles.py` reproduces `comparison.json` from exact raw references.

- Stock: six batches captured at actual sleep100000µs; median interval66.329s.
  Turn interruption killed the session before idle/final exit proof. PID was
  absent afterward, which does not substitute for native exit or Job proof.
  `stock-interruption.json` keeps that limitation. `paired_diagnostic_completed`
  remains false. No automatic rerun or invented PASS.
- Responsive:6×50+idle completed, actual editor52044 exit0; outer target45400
  and wrapper13520 exit0, source unchanged, owned tree/handles released.
  Median interval23.895s, observed ratio2.776. The first four points were focused,
  last two plus idle unfocused; all read back6900µs. This supports consistent
  cadence, but is not a controlled identical-focus benchmark or whole-run speedup.
- Responsive handle counts574,566,566,566,559,561, then558 after idle. The last
  workload delta is one Event plus one IoCompletion; idle removes two Events
  and one IoCompletion. Stock batch4→5 has net one Event plus one Thread, with
  other handle-slot churn. Numeric slots are not stable object identities.
- Object counts71123/resources6 held during all twelve captured workload batches.
  Idle has two extra Objects while the diagnostic timer/coroutine remains active;
  their exact ownership is not established. The production gate is not satisfied
  merely by this supplemental observation.

`responsive-modules.json` and `responsive-thread-modules.json` only map thread
start addresses against one owned-process module observation. Many starts resolve
to a CRT wrapper; this does not identify their caller or prove a leak source.
192 entries per snapshot lack valid type metadata and remain unclassified.
PSS self-tests01/02 failed a trailing-NUL assertion;03/04 passed. Preserve both.
The stock outer01 failed prelaunch because its timeout exceeded the runner cap;
no native process was spawned. The actual stock run is owner02.

Microsoft documents validity flags, byte lengths and thread start addresses in
[PSS_HANDLE_ENTRY](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_entry).
System thread pools manage asynchronous work and waitable handles;
[Thread Pools](https://learn.microsoft.com/en-us/windows/win32/procthread/thread-pools)
provides context, not evidence that a specific observed handle belongs to a pool.
Reserved PSS fields are not used to infer identity or retention.

## HTTP attribution

`profile_http.py` delegates unchanged journal methods and stream operations;
instrumentation itself adds overhead. The existing S73 driver checks the original
33,224,600-byte history and a fresh private copy, receipt/readback and source hashes.
`http-owner-01/`: actual target10532/wrapper24524 exit0, clean owned tree.
30/30 inspections completed; terminal p95466.165ms, max response gap308.506ms.
The earlier2s failure did not recur in this short lane; it remains unresolved.

`http-attribution-timing.json` reports inclusive times:122 snapshots10.683s,
read2.424s, open0.330s, fsync0.169s. The residual includes hashing, metadata,
scheduling and wrapper overhead; it is not a pure measured hash duration.
The33.018s initial load includes full accepted validation. Parent and child times
overlap and must not be added. Do not extrapolate30 reads to the1000-command mix.
The private33MB copy stays under this directory locally but is excluded from Git;
the original remains untouched and its exact hash is in the retained report.

## Negative guard and remaining work

Five variants cover an obsolete key,100000µs, float instead of integer, integer
instead of bool, and a missing focused key. `cadence-guard-verification-*.json`
are produced only after actual exit86, exact failure code, INACTIVE/empty partial
state, unchanged scene and clean Job verification. Early scan-abort warning is
allowed only by exact bytes in these rejection lanes, never in positive/full runs.
The first old-key collector erroneously expected an empty output directory;
`failure.json` is required negative evidence. Corrected verification reuses the
native raw without re-running the engine, retaining the failed collector result.

Next: investigate retained-counter definition/cause and host latency with bounded
diagnostics, then freeze a new campaign. Preserve the original workload/gates;
do not simply retry the full campaign after this speed fix. Final acceptance needs
10×35 complete batches and two independent PASS/TICK=yes on the same final closure.
Three workers completed the initial S76 analysis; subsequent two follow-ups failed
with workspace-credit errors, and no new independent review was produced.

GT01–05 do not establish unrestricted2D/3D game authoring. The current Godot
authoring fixture restricts scene nodes; Blender→GLB success does not establish
Superfighters-like gameplay, HH World multiplayer or a finished game. GT07–10,
including real Android, remain; HH World has its separate plan after GT10.
