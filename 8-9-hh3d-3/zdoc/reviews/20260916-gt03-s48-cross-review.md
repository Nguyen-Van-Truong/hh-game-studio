# S48 bounded cross-review

AUTHORITY=0. FORMAL_GT03_VERDICT=NONE. ENGINE_RUNS=0. CONTAINER_RUNS=0.

Read-only source review on 2026-09-16, Asia/Saigon; observed HEAD
`933c13491f10d9ecc738cf465968c1b2dba9a4c5`. Only this report was written.
The lanes were actively implementing during review. Hashes below identify the
reviewed cuts, not an accepted combined closure. No code change, commit or tick.

## Findings delivered to the owning lanes

1. **P2 — A stream-reader exception can be mistaken for a complete log.**
   Executor draft `0a201509…`, `linux_executor.py:160–217`: `drain()` does not
   capture exceptions from `read1`. An OSError can end a thread, making
   `readers_stopped=True`, while `_cli_clean()` has no reader-error/normal-EOF
   check. If the CLI exits zero and its Job drains, truncated stderr can feed a
   false `diagnostic_process_clean`. The exceptional cleanup path also closes
   the Job without a final reader join/stream-close/ownership reconciliation.
   Sent to the executor worker: record per-reader errors and normal EOF, require
   both streams to complete, and retain/report incomplete cleanup. This cut is
   not proof of a clean engine stream. Worker repairs require a new reviewed hash.

2. **P2 — Fixture identity was stamped rather than checked against executed input (source repair rechecked).**
   Rechecked probe `b15a6fe4…`, `case_observation`: the row derives
   `fixture_script_sha256`, mode and timeout from the requested case, but does
   not compare them with the executor's actual input manifest/snapshot or its
   recorded mode. A raw result/log directory from another case can be relabeled
   by generating a new observation. Require the exact expected script hash and
   mode to match executor evidence; also bind the fixed scene/project template.
   Sent to coordinator. The exact artifact inventory protects already saved
   observations from ordinary edits, but does not establish this attribution.
   Coordinator's later `d413ef2a…` cut now compares all three actual snapshot
   hashes and `input_hashes_before` against the fixed fixture, plus actual mode
   and timeout. Static recheck finds this defect addressed.

3. **P2 — Resume trusted the claimed closure digest (source repair rechecked).**
   Same probe cut, `main` resume branch: `binding.files` and `run_id` are checked,
   and frozen source files are hashed, but `binding.source_closure_sha256` is
   not recomputed from that verified map. A wrong claimed digest can be copied
   into new observations/capture during resume. Recompute with the same locked
   closure algorithm and reject mismatch before continuing. Sent to coordinator.
   The later `d413ef2a…` cut recomputes the closure digest and includes it in
   the resume equality check. Static recheck finds this defect addressed.

4. **P2 — Cached reducer module may come from another source closure.**
   Journal draft `7b5f772b…`, module loader: fixed
   `sys.modules['_hh_gt03_publication_state']` is reused without checking its
   path/hash. Loading a second checkout or frozen snapshot in the same Python
   process can silently use the first reducer. A fresh isolated test process
   avoids this condition, but the wrapper API does not enforce it. Sent to the
   journal worker: derive the cache key from the resolved sibling source/hash,
   or fail on a cached binding mismatch. No accepted-core change is needed.

These concern diagnostic/source attribution and cleanup; existing explicit
`public_ack=false`, `sandbox_acceptance=false` and
`validation_attribution_proven=false` correctly prevent treating the probe's
observations as publication or sandbox acceptance.

## Earlier findings and source recheck

Initial probe `a7201376…` trusted `diagnostic_process_clean` despite contradictory
actual exit/timeout/cap fields, accepted a callback marker as a substring, and
resumed saved verdicts using an arbitrary saved artifact map without raw
re-evaluation. One `python -B` inline, memory-only evaluator invocation returned
`fixture_observed=True` for both:

* `diagnostic_process_clean=True`, container exit 37, host timeout/cap true;
* failed host plus stdout `prefix HH_PROBE_TOOL_ENTERED suffix`.

No engine/container or test fixture file was created by that reproduction.
Coordinator changed the code. Static recheck at `b15a6fe4…` finds actual
completion checks, exact callback/busy markers, raw result/log re-evaluation,
complete artifact inventory comparison and explicit source/case fields. The
original three defects are addressed in that source cut. Added negative tests
were read at `8297fc8c…`; this reviewer did not execute those changing tests.
Findings 2–3 describe binding gaps in that intermediate cut. One further
coordinator-requested static recheck at `d413ef2a…` found both repaired; updated
negative tests were read at `42b3db5a…`. Coordinator reported nine passing tests;
this reviewer did not rerun them. Executor-reader and journal-loader repairs
remain outside the reviewed cuts unless their owners provide new evidence.

## Contract and reducer observations

The reviewed catalog requires project CAS in every non-inspect payload and
nested preview mutation, preserves the envelope scene revision, checks the
trusted selected-bundle revision and strips the project field from the narrow
engine projection. Preview reports both revisions; script-only stale-project
coverage exists. No new blocking error was found in that changed contract path.
It remains pure validation, with no public mutation capabilities enabled.

The existing pure publication reducer (`cee38e70…`) still preserves original
admission, separately binds semantic/project revisions, retains one pending
command, holds UNKNOWN without a resume API, and changes last-good only after
its internally consistent COMMITTED sequence. No new critical reducer defect
was found during this integration read. Its synthetic observations remain
unproved until an engine owner independently verifies them; durable storage of
those observations does not turn them into actual engine evidence.

**Full project closure remains a separate explicit gap.** The coordinator's
new trusted editor fixture attaches a known non-tool script with an exported
value and preserves generated `fixture_actor.gd.uid` in evidence. The reviewed
two-content bundle/reducer does not include `.gd.uid`, project configuration,
or trusted addon/UID metadata in its published file set. GT-01 treats UID files
as source. Scene/script content hashes alone therefore cannot claim a complete
reopenable Godot project publication. Retain this as future owner/consumer
integration work; no file-set expansion or GT-03 acceptance is authorized by
this S48 checkpoint. Reading the new probe's source is not a substitute for its
future actual edit/undo/reopen evidence.

The executor draft's default contract is appropriately restricted: exact
project files/template, pinned binary/image/helper, read-only mounts/root,
bounded tmpfs/process/memory/CPU configuration, owned container name/ID checks,
and separate removal verification. Actual Docker inspect representation of
mount paths, environment, security options and healthcheck is still a runtime
API assumption at this cut. Strict mismatches should remain setup failures;
do not relax them based only on flag spelling. This reviewer ran no daemon or
container preflight. The diagnostic network fixture uses a non-reachable test
address without a reachable positive control, so it is not a complete network
denial proof. Child markers remain untrusted, and a child printing a forged
success marker must never authorize publication.

## Exact reviewed hashes

Paths are relative to `8-9-hh3d-3/studio/`. Initial source hashes were recorded
at 2026-09-16T23:55:08+07:00; the executor and probe repair cuts were read later
in this same bounded review. Subsequent modifications are outside these cuts.

```text
godot-addon/contract.py bc34eac25f2e03a026c89e7cb77ee56bb7244559c518c6b432d306ba43d41b1c
godot-addon/operations.json 8c42540668be350e5dc67a384fd077de7606c0e54deef3e40bba52c7f788c61c
tests/godot/contract_vectors.py 09438438e866930c363dc54d3b5d01219e6958c910feb69e68c1142d29baab54
tests/godot/test_contract.py ba6accdc1606da6f519f3e5b4600d43bd5f6bc25f090f2cac779b90f731f622b
tests/godot/run_editor_probe.py e3d17f3f0bb6da06eb194c35f5f6e7c08b81c633713fc2b84ad765c411354d7a
tests/godot/linux_probe_fixtures.py db77771b8e136de2f7c81c42249cca29e5748d064364a14a696c3308522e3d4f
godot-addon/publication_state.py cee38e70be71c0d143dff7fa07103246bbbec0ea9d56e7d51ed4fb1077e5fbf1
godot-addon/publication_journal.py 7b5f772b730f2b1cb58e241d13ea49ae4f821fcdf5b7745263e3e2df920124c6
godot-addon/linux_executor.py 0a201509d6ea160646a96cd59a41c77bf749e440830f98f4222dbee8a205255d
godot-addon/validator-toolchain.lock.json 2cfb076917b162cb053e98eefc7c97632b6970acb782a892c64a2c91cf134614

BEFORE tests/godot/run_linux_probe.py a7201376014197da85e1377a1719d853012d1e8c343935a4d13a195e0f140c78
BEFORE tests/godot/test_linux_probe_evidence.py 7ba8aceaec4f31d7b6dd8a8950ed1035082db6cb64bcbbce08ebf5a10f031c08
RECHECK tests/godot/run_linux_probe.py b15a6fe4977e3ebb92bbc63a7b4031417a76dcf19ec577e8b4a3a25c03b149cb
RECHECK tests/godot/test_linux_probe_evidence.py 8297fc8c006d4d014ed9f26a0e89db426557be66269d53fb7a0dacf66596c555
FINAL_STATIC_RECHECK tests/godot/run_linux_probe.py d413ef2ab53828f4ac337289280aca130617d1bbc96737480e22b69c4b269dbe
FINAL_STATIC_RECHECK tests/godot/test_linux_probe_evidence.py 42b3db5aeb9421c2bd1d19705002f8e2ce2d0635ceb017a026389eb61b6a3fed
UID_GAP_READ tests/godot/run_editor_probe.py 94e875368aa30057b760fe1ce257182c7e846b7779d8e778af89e08cf4766380
UID_GAP_READ tests/godot/editor_probe.gd bcd13de384c328e3f8509be4407a9894c7403a44077b7341ede7f0aa406b4fd5
```

S48_CROSS_REVIEW_END
