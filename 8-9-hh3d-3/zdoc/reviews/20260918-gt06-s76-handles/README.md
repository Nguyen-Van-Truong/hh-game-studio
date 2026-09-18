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

Next: run the first integrated campaign against the guarded S76 cadence after
the completed retention and HTTP diagnostics below. Preserve the original workload/gates;
the cause of the earlier rare HTTP gap and handle increases remains unproven. Final acceptance needs
10×35 complete batches and two independent PASS/TICK=yes on the same final closure.
Three workers completed the initial S76 analysis; two older follow-ups failed
with workspace-credit errors. Three fresh Astra xhigh diagnostic reviewers were
successfully dispatched on 18 September. These are not final acceptance critics.

## Completed retention probe and next integrated measurement

`analyze_retention.py` verifies and copies the finished `gt06-s76-retention-01`
raw evidence into `retention-evidence/`; `retention-analysis.json` retains the
exact copy inventory, nine PSS points and cycle checks. All800 native semantic
cycles completed, editor25368 actual0, import34140 actual0; outer target37480
and wrapper30776 actual0. Jobs zero/closed, retained native handles released,
source unchanged, logs clean. Scheduler terminalstate3/result0/noinstances was
recorded separately in `retention-terminal-task.json` before deleting that task.
The123 copies include16 isolated appdata/localappdata cache files retained only
locally under the repository's existing ignore rules. Git carries107 retention
copies; the verifier uses the declared local raw domain and does not claim a
standalone Git-only reproduction of those caches. No cache ignore was overridden.

Handles:573,565,565,557,559,559,559,559, then559 at idle. Batch3→4 adds an Event
and IoCompletion; neither the count nor repeated numeric slots establish object
identity or ownership. They remain at the last idle point. Objects71125 except
batch2 and idle71127; resources6 throughout. Batch4 and three subsequent samples
are stable. Median100-cycle batch32.464s; maximum native statusgap578.721ms.
No HTTP mix, RSS proof, full benchmark or leak-free acceptance is claimed.

The diagnostic source map has39 files, closure
`aa58e8ee7fc4f8399766c8d6beca9dfc1bf10b5247ab7f2aba5cb0d40c259b6f`;
every dependency is an exact subset of the49-file current campaign map. Its
disposable instrumented plugin has its own project hashes. Do not relabel this
diagnostic as a full campaign source closure or reuse its samples there.

The earlier responsive arm's net561→558 drop also does not show that its newly
added Event/IoCompletion pair was released: different numeric slots disappeared.
See the new independent retention report for this correction. Windows documents
that completion ports can serve several I/O handles and require closing all
references; the [API documentation](https://learn.microsoft.com/en-us/windows/win32/fileio/createiocompletionport)
does not identify the creator of these particular observed handles.

The next run is a new candidate under S76 source, never a resume of failed S75.
It retains10×35, exact mix, original warmup, RSS/counters/status/p95 limits and
fail-closed behavior. An integrated failure is preserved and diagnosed before
another launch. A speculative transaction optimization is deferred: the rare
S75 timeout happened after admission, and a new lock abstraction would invalidate
otherwise reusable transport evidence without yet proving that failure's cause.

## Campaign startup and bounded resume

`gt06-s76-campaign-01`, launch1, started00:04:45UTC and failed before any batch:
the shared import owner enforced20s while Godot was loading global class names.
The import native26944 has no captured exit; its helperexit2 is recorded separately.
Host23948 actualexit1, host/import Jobs zero/closed, host owner handle released.
Scheduler terminal1/noinstances is in `campaign-launch-observation.json`.
`campaign-import-failure-01/manifest.json` seals146 exact copies with zero samples.
`preserve_import_failure.py` verifies source/workstation/Stop/cleanup prerequisites.

The independent import review found no source/project/config mismatch: all39
shared dependencies match; the only relevant project differences from the clean
retention run are its instrumented diagnostic driver and ignored input binding.
Retention import completed7.953s; older same-depth campaign imports completed
4.782–9.171s. This does not establish the cause of the new20s stall. The fixed
20s safety bound remains unchanged, as do CPU/memory/workstation settings.

One fresh process pair resumes the same frozen campaign as **launch2**, dispatched
00:08:36UTC under `HHStudio.GT06.gt06-s76-campaign-01-launch-02`. Live status must
be queried before calling it running. No old partial samples are used. If import
or the unresolved measured failure repeats, do not automatically launch a third
attempt. Preserve evidence and diagnose the new phase first.
At00:09:35UTC a separate live observation confirmed one running scheduler
instance, host40900/editor38684 and matching command/native progress. Import10272
finished in5.797s with actualexit0/clean Job. This observation does not retroactively
explain launch1's stall and does not predict later campaign success.

The first ad hoc workstation prerequisite check compared Python's OS tuple to
the saved JSON array and rejected before copying evidence. The preserved verifier
uses the runner's exact JSON representation; the workstation is unchanged.
No native run was repeated to repair that collector comparison.

GT01–05 do not establish unrestricted2D/3D game authoring. The current Godot
authoring fixture restricts scene nodes; Blender→GLB success does not establish
Superfighters-like gameplay, HH World multiplayer or a finished game. GT07–10,
including real Android, remain; HH World has its separate plan after GT10.
