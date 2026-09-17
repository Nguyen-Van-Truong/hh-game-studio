# GT06 S71: fix retained Output display objects

GT01–05 remain accepted; GT06 remains in progress. No acceptance verdict is
created here. The S70 campaign02 has zero successful full runs. Its first
measured sample correctly failed on editor ObjectDB growth, not host memory.
The failed attempt and actual cleanup evidence are preserved in
`campaign02-failure/`, with full raw data retained locally.

The last three native object deltas match displayed stdout paragraphs plus
one editor-only UndoRedo action paragraph per cycle. See
`retained-object-growth.md`, `line-attribution.json`, and the independently
written `host-retention-analysis.md`, `measurement-contract-review.md`, and
`output-cap-contract-review.md`. These are implementation analyses, not the
two final independent acceptance reviews.

The correction changes only `run_native_benchmark.py` and
`benchmark_native.gd`: generated projects freeze the stock
`editor_overrides/run/output/max_lines=100` setting before import; native
bootstrap requires an effective integer readback of exactly100. The accepted
adapter, semantic operations, raw counters, complete external logs, full
workload and acceptance limits are unchanged. This bounds displayed paragraph
Objects only. Internal message strings remain retained and all RSS checks stay
active. Results apply to this declared configuration, not default10000.

`output-comparison/` verifies two disposable3×50-cycle native diagnostics:
default-cap10000 objects71110→71182→71254; cap100 objects71109→71131→71131.
Resources remain6. Each native target/helper exited0 with checked owner
cleanup. This demonstrates a post-fill plateau in this short comparison;
it does not replace the full host/native benchmark or prove later RSS limits.
These pre-fix diagnostics have their own frozen source/project maps and the
documented omitted non-Python schema dependency; they are supplemental only.
Reproduce against the recorded pre-fix source, not the changed live drivers.

`native-fixed/` retains the unmodified new native driver's one-cycle positive
diagnostic: import/editor exits0, clean stderr, verified scene save/reload and
closed/zero Jobs. `output-guard/` preserves a deliberately wrong setting101:
bootstrap rejects before any cycle/batch, actual native/helper exit86, scene
unchanged and Jobclosedzero. Its `Scan thread aborted` warning is preserved;
this negative lane is not a clean success lane. The original negative collector
expected empty stderr and failed after checking the guard; verification was
recovered from its completed raw capture without rerunning Godot. The first
comparison collector similarly used `batch_index` instead of native `index`;
its original script and failure remain, and only the collection was repaired.

`../20260918-gt06-s71-units-01/` records79 affected timing/profile/campaign/
assembly/launcher tests, all passing in49.540s with actual child/helper exits0,
verified tree cleanup and unchanged source. Counts are not additive with older
runs. Final full measurement must use a fresh campaign ID and the complete
campaign source closure, which explicitly includes the schema and launcher.
No S70 partial samples or prior acceptance signatures transfer to that run.

Source checkpoint `bb881a4a` was dispatched as `gt06-s71-campaign-01`, launch1,
at02:10:39 local. The02:13:35 observation confirms a running scheduler instance,
warmup batch2 in its command phase, and empty supervisor/host/editor stderr.
The first warmup took56.228s and all six artifact references match. The49-file
campaign map matches live/frozen/Git bytes at closure
`38a0848b68c4d6b34f1a03839008d54aa9e99a33458abaa88a939c8d2a744d86`.
See `campaign-launch.json` and `campaign-launch/`; this is startup evidence,
not a completed run. Requery live task state on resumption. The existing
15-minute heartbeat was updated in place, recorded in `overnight-schedule.json`.
