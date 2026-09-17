# S71 final sealing preparation

Preparation only, 2026-09-18 Asia/Saigon. No acceptance, critic signature, gate
change, test execution, engine launch, source edit, staging or commit. This
directory is the only write scope. Paths in the recipe are relative to
`8-9-hh3d-3/` unless a different domain is explicit.

The selected campaign is `gt06-s71-campaign-01`, frozen at `bb881a4a`, with
49 studio-relative dependencies and source closure
`38a0848b68c4d6b34f1a03839008d54aa9e99a33458abaa88a939c8d2a744d86`.
At preparation, a bounded top-level listing found only `campaign.json` and
`benchmark-profile.json`; final capture/dataset/summary and supervisor return
were absent. This is a preparation-time observation, not a live status claim.
The caller reported a running partial first run. No partial count is PASS.

## Deliverables

- `collection-recipe.json` is a machine-readable collection specification. It
  names the existing validators, exact map equality rules, evidence groups,
  hash domains, pending outputs and review sequence. It is not a final manifest.
- `verify_campaign_readonly.py.draft` is an **unexecuted** thin adapter around
  the existing run/ownership/BoundRun/profile validators. It first requires
  terminal campaign artifacts and a separately collected terminal scheduler
  status. It never calls a campaign runner, launches an engine, resumes work,
  writes measurement files, or issues acceptance. It prints only a verification
  report. A coordinator must review it before using it after measurement.

Do not execute the adapter or do a full evidence-tree audit during the measured
campaign. A full raw hash pass is intentionally deferred until the native lane
has reached a terminal state. Do not use `run_benchmark_campaign.py` as a
read-only verification command: its main path can launch/resume native work.

## Existing checks reused

`run_benchmark_campaign.verify_run_capture` re-hashes every recorded selected-run
artifact and joins context, source, process identities and captures. It calls
`verify_owner_captures`, which uses `benchmark_job.verify_capture` for the host
and editor and `pipeline.native_job.verify_captured_stage` for import. Capture
v2 checks raw actual target/helper exits, configured/closed/zero untainted Jobs,
wrapper-handle closure, exact invocation/source/binary/profile bindings. A
caller-supplied cleanup JSON or scheduler exit cannot replace this chain.

`benchmark_assembly.assemble_run` validates all 35 batches, their six artifact
classes, native index/ready/start/ACK sequence, continuous identities and
native state, full logs, frozen source and cleanup. It returns `BoundRun`.
`assemble_dataset` requires bound runs sharing source/toolchain/profile;
`benchmark_profile.summarize_dataset` enforces the unchanged exact v2 profile.
The adapter compares their re-derived data to the existing producer output;
it does not mint a new dataset or combine partial attempts.

The earlier GT05 `freeze.py` and `verify.py` are scoped to GT05. Their explicit
source/review/raw-domain pattern is useful, but they are **not** GT06 validators
and must not be run against a fabricated GT06-as-GT05 manifest. The S71
`verify_source_checkpoint.py` already verifies exact campaign Git bytes and
must be reused for that check rather than duplicated.

## Collection sequence after completion

1. Obtain terminal scheduler status with the existing launcher `status`
   operation for every actual launch; retain launch-specific receipts. Join the
   final launch's return code and terminal task instance. `return.json` explicitly
   precedes supervisor exit. Preserve scheduler status before task deletion.
2. Verify source equality using the existing checkpoint helper with `bb881a4a`
   and a new output path. Review and run the draft adapter with the same pinned
   Python console binary as the campaign, passing the final status file and
   launch number. Capture its real exit/stdout/stderr as new review artifacts.
3. Expand the selected campaign and inherited inventories named in the recipe.
   Hash exact raw bytes once, retaining every declared artifact (including empty
   logs) and disclosing excluded/unselected failure attempts. Check all source
   projections, plus added/removed dependency paths, before allowing lane reuse.
4. Resolve F01–F15 from the S70 requirement draft using the F11/F12 supplement and
   S69 integration follow-up. Historical fault/repair evidence keeps its old
   source; S69 managed replay bridges to current functional runtime. The final
   matrix must link the exact accepted GLB producer/import to the consumed GLB,
   preserve diagnostic labels and retain all stated fault/Android/GT07 limits.
5. Freeze one explicit candidate manifest and requirement matrix. Snapshot the
   applicable governance files; do not hash mutable progress files in place.
   Hash source, review, raw and any portable view as separate domains. Retain a
   physical raw locator and ensure both critics can access it. A portable text
   rendering cannot replace binary or original raw bytes.
6. Give both independent read-only critics the same final manifest byte hash,
   source domains, requirement matrix and verifier report. Their verdicts remain
   outside the already-frozen candidate manifest, preventing a circular hash.
   Any candidate/source change invalidates those reviews for the changed hash.
   Only the coordinator can subsequently record acceptance/tick.

## Source reuse and failure boundaries

`git diff --name-only 9bc28b6 bb881a4a -- 8-9-hh3d-3/studio` lists exactly
`tests/replay/benchmark_native.gd` and `tests/replay/run_native_benchmark.py`.
S71 fixes the project output display cap before import/freeze and checks its
native effective value. It does not change accepted adapter/functional source.
Keep the complete external logs, unchanged RSS/counter thresholds and cap100
disclosure. Native negative setting101 and its warning remain negative evidence.
Source-list equality is still required at seal time; a historical assertion of
unchanged dependencies is not a substitute for that comparison.

S70 campaign02 remains failed. Its partial measurements cannot enter S71.
Within S71, only a complete selected attempt for each index0–9 can enter the
dataset; failed prefixes stay inventoried and excluded. Actual Stop has its own
stopped/cleanup result and is never promoted to natural native exit0. Retain
baseline434/434, affected66/66, S70 affected75/75 and S71 affected79/79 under
their distinct invocations; do not sum overlapping suites. The accepted S64
dependency's 232 pass plus one symlink skip stays a skip.

The adapter verifies the campaign portion only. It is not a complete GT06
sealer: inherited functional artifacts, per-lane closure completeness, supervisor
XML/registration chain, failed-attempt forensics, final review/raw manifests and
both independent critiques are explicit remaining recipe steps.
