# GT06 S69 requirements and evidence mapping

Read-only review of implementation/evidence, followed by this report only.
Observed 2026-09-18 00:37 Asia/Saigon at checkpoint
`c5e56c7e05e5bf784d1e67741cd44cd18b6bd493`. No source/plan edits, tests,
engines, subagents, acceptance signature or gate change. Authority remains
`zdoc/8-9-godot-blender-agent-studio-plan.txt` S68: GT06 IN_PROGRESS;
GT01–05 stay accepted at their own refs. Paths below are relative to
`8-9-hh3d-3/`; abbreviated raw run paths begin `studio/.local/reviews/`.

## Requirement map

| Requirement | Actual retained evidence | Remaining work / limit |
|---|---|---|
| Blender edit → validated GLB → Godot import → Play | Accepted `zdoc/reviews/20260917-gt05-s63-audit/manifest.json`; `studio/host/replay/native_runner.py:69` binds accepted input bytes before import; S65/S68 captures bind GLB `e85e536137208ba84adbc875b6fb647b5a4e49156344e03e2e8947a7ae91e377`. | Join the accepted producer/edit/import evidence to this exact input hash in the final matrix. Do not rerun GT05 because unrelated GT06 files were added. |
| TQ06 real 60 Hz input, seed/edges, menu/move/outfit/emote/prop/pause/resume/quit | `gt06-s68-reviewer-complete-02/observation-checks.json`: all semantic predicates true, movement 1.50000023841858 m, simulation frozen while paused/UI advances. | Retain: all 173 declared source entries and all five reviewer/probe entries still match. |
| TX13 capture source/PID/time/camera/freshness | Same run's `capture.json`, `project/out/report.json`, seven PNG bindings and `reviewer-probe/result.json`. | Retain. Inspection is historical; do not claim a live debugger. |
| Seeded fault → authenticated repair → replay | `gt06-s65-native-04` → `gt06-s65-repair-02` → `gt06-s65-native-05/repair-replay.json`; observed zero movement before repair and 1.50000023841858 m after it. | Preserve the causal chain. A fresh managed replay using the retained repair02 receipt can bridge the changed runtime focus policy; the existing `repair_replay.py` supports this. Repeating the authenticated repair is unnecessary solely for the two unrelated-to-repair runtime changes identified below. |
| Versioned performance schema/raw frames/percentiles/1% low/counters | S65 native04/05 `perf-export-v1.json`; `studio/tests/replay/test_perf.py:164–167` rejects missing schema identity/1% low; S68 units-03 covers replay tests. | Exporter/schema bytes unchanged. Retain as diagnostic data, with startup unavailable values and screenshot overhead declared; this is not the tools UX benchmark. |
| Section 2.6 reviewer keyboard, pending/unknown/error next action, Stop/reconnect | S68 reviewer complete02 and stop02, `studio/reviewer/README.md`, reducer/client tests in `zdoc/reviews/20260917-gt06-s68-units-03/`. Actual Tk Play/Inspect/Capture/Esc and clean exits recorded. | Retain current-source GUI evidence. Unit coverage supports error/reconnect states; do not claim every state was exercised through native GUI. |
| TX02/05/13/18 congestion/revocation/stale result/priority Stop/ownership | S66 saturated-stop04, revoked-result01, stale-capture01; S68 GUI Stop and owner-smoke02; journal contract03. | Refresh the three adversarial service lanes because service.py changed its Journal implementation. Reuse already-current GUI Stop. The new owner findings below also need fixes and focused regressions. |
| Exact tools UX benchmark | S68 campaign/assembly/profile implementation, partial diagnostics; coordinator owns campaign03. | Still requires 10 fresh process pairs ×35 complete batches: five warm-up plus 30 measured per pair; 350,000 mock commands and 35,000 native cycles total. Require actual exits/Job-zero, source/profile binding, raw metrics, p95 inspect/Stop ≤500 ms, status gaps ≤2 s and memory/effect/leak checks. Interrupted campaign01/02 prefixes cannot contribute samples. |
| Frozen candidate and two independent critics | S65–S68 progress packages explicitly deny acceptance. | Assemble one candidate manifest with per-lane dependency/evidence mapping and fresh independent reviews of that candidate. Whole-manifest differences from unrelated additions do not by themselves require rerunning unchanged lanes. |

## Fresh owner-review blockers

Coordinator reported two new owner-review findings while this mapping was
prepared: **constructor cleanup provenance loss** and **wrapper handle leak**.
Both are **unfixed at this report's snapshot**. This report does not independently
reproduce them or substitute for the owner's detailed review.

Fix both and verify the affected constructor/error/cleanup/handle paths before
final benchmark acceptance. A completion banner or otherwise good timing cannot
waive owner provenance/handle cleanup failures. Keep campaign03 and earlier raw
artifacts under their actual source bindings. If the fixes alter benchmark owner
dependencies, affected official measurements must be bound to the fixed source;
do not relabel old measurements. This is not a reason to reopen GT01–05 or repeat
unchanged GUI, repair or performance-schema evidence.

## Exact dependency comparison

Each lane's recorded `source-files.json` was parsed and **every listed file**
was SHA-256 compared against current `studio/` bytes. This is a listed-dependency
comparison, not a claim that an old manifest contains later-added dependencies.
Manifest SHA hashes raw JSON bytes. Source-closure SHA uses the repository
algorithm: ordinal path order, each `path + NUL + digest + LF`, then SHA-256.
No test or engine was executed to perform these reads.

| Lane | Manifest group | Entries equal / listed | Changed files |
|---|---|---:|---|
| `gt06-s65-native-04` | A | 152/154 | D1, D2 |
| `gt06-s65-native-05` | A | 152/154 | D1, D2 |
| `gt06-s65-repair-02` | B | 154/156 | D1, D2 |
| `gt06-s66-service-complete-01` | C | 168/171 | D1, D2, D3 |
| `gt06-s66-saturated-stop-04` | C | 168/171 | D1, D2, D3 |
| `gt06-s66-revoked-result-01` | C | 168/171 | D1, D2, D3 |
| `gt06-s66-stale-capture-01` | C | 168/171 | D1, D2, D3 |
| `gt06-s68-reviewer-complete-02` | D | 173/173 | None |
| `gt06-s68-reviewer-stop-02` | D | 173/173 | None |
| Both S68 runs' `reviewer-probe/source.json` | E | 5/5 each | None |

Groups A–D refer to each run's `source-files.json`; E refers to
`reviewer-probe/source.json`. Exact identities:

```text
A manifest_sha256=5103ec7ea27c64450fe05951de102ec639a9ad3cc8f11cccfeacfa0d91c11ab5
A source_closure_sha256=58710f5d13a31190accfe8addb7fcb4885e3ee831a8a5152b4917cc9a103959f
B manifest_sha256=8f986d550d57daa8beb9d35a6ff67e4af056673e9f410107fea24db9c399bf7f
B source_closure_sha256=ecbbffb5406748704318e2b08fd2a6a86e279f9355f3cf78e2f419993d39f43a
C manifest_sha256=b33fdd75744fb446229716fe2f8024bf702afbcfde86fe4141fe5731bd13a01f
C source_closure_sha256=2c623754803e14d59f5d143b3964443a73d21eadaf5947d91fd4a83423e34da2
D manifest_sha256=76e3172e9b4b9be6a3b703685213ad2d96b705a923a7955545ca1002d4dd2b53
D source_closure_sha256=153926756107745108aa0df1941b6a189a77dd0a814f2424cd24c3a489abed7b
E manifest_sha256=4476fe477abab0859f9957403d84ab3a869db458f46b4ff251672ffc560df640
E source_closure_sha256=7665621f1090836c2bc711ccc7f6857c3961b99be5b077292baaadc933b712fb
```

Exact changed dependencies (paths relative to `studio/`):

```text
D1 fixtures/play-observe/project.godot
recorded=e91d3fc6a99c67982e33dbb20a2b80e6e1188b2cafb0fb096a982542f5f09e80
current =e97f22356c828f1fec7737f63cd01e64490455895c19f477a8c362e5a8364b2f
change  =window/size/no_focus=true plus explanatory comments

D2 godot-addon/observe/trace_bridge.gd
recorded=9eabb7326f39a1d694ff7b828759f6a647406e077dde81ba8ed099aa8135ae16
current =f66a649117217562cae1add178109490eb4b890557ce38555e66962f9e2d15d0
change  =native WINDOW_FLAG_NO_FOCUS guard before authored trace execution

D3 host/replay/service.py
recorded=64637da0b8b9896c1e6a2dfa125e6fcd75fde0afdf987257969b4bde86115c3b
current =a09641c7954938aebf1207bd37bf66825eb483e51e7c386032b09fcde496121a
change  =accepted core Journal import replaced by VerifiedJournal alias
```

The new `host/replay/verified_journal.py` and `journal_index.py` dependencies
were absent from group C and are bound by group D. All five group-E hashes
match current bytes:

```text
reviewer/app.py=5fad7a8f226176cd64b139afb7334c0d3ad2e630a80bae96b20be02b71e212e9
reviewer/client.py=843a6c2743eef5f85ed45f24bbe3054a187afaec1658cb9447ff046e0f83508d
reviewer/main.py=2e6190fb28b81c50aae110694d74fddc6a0f7f1115156333e972311bfa94666a
reviewer/model.py=27459fe77d8307f8848f6d4a9969d17c659259013aa4627aa461582b4a37f7ec
tests/reviewer/run_reviewer_probe.py=d4bbb761406bce223178e83f96164f65f459aa138f958212267bf68eb69002ba
```

Selected unchanged semantic/driver hashes supporting reuse:

```text
host/replay/repair.py=dc1aa96c4f68633dcd22225d65f18609c294a7bd485b0b534d2096b36542ec07
host/replay/repair_replay.py=3b8d842105ad4e1e5e55fc4a36e5a32e5095a462274144c4457c1fa4cdee5375
host/replay/observation.py=f6ea8900f3c37737deef0c28387cd69f5f1bd5b13419333c75dfb0cd53e31a20
host/replay/perf_export.py=d20c3b0505206cb4d5ba8fcbe5eede8281954d76b1757ce99f03cdb81bb017c2
tests/replay/run_service_probe.py=436c965f06beef99ec2b3c10817aa9e098063ad9cf80db48d1fdc40f62a53d32
```

## Fastest valid remaining sequence and later external gate

Coordinator owns native execution. Preserve the current campaign's raw record;
resolve the two owner blockers, run their focused regressions and obtain exact
benchmark evidence on the final affected closure. Serialize affected service
adversaries and the managed replay bridge; retain already-passing unchanged
lanes. Then assemble the candidate and obtain two independent reviews. This
mapping is not either acceptance review.

Android remains a later GT08 hard gate, not a desktop GT06 blocker.
`zdoc/reviews/20260917-gt06-s66-downstream-preflight.md` records scoped SDK/adb
discovery gaps and **unverified** device attachment/authorization; it does not
prove no physical device exists. GT08 requires a reviewed Android toolchain and
actual install/launch on a supported physical device with SKU/OS recorded.
Missing that evidence blocks GT08/09/10 acceptance and HH World handoff.
Emulator or desktop-only evidence cannot replace the physical-device gate.
