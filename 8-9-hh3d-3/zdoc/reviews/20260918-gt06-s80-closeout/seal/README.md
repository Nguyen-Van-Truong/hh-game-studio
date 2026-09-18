# S80 offline sealing preparation

AUTHORITY=0. Draft only; no validator execution, raw hash audit, engine, test,
runtime edit, verdict, tick, or acceptance. Only syntax parsing is permitted
during the active campaign. All paths below are relative to `8-9-hh3d-3`.

This adapts the S73 seal adapter and S70 packaging requirements. It binds
`gt06-s80-campaign-01`, source checkpoint `f75a5d08`, exact 50-file closure
`1dc889ef923dee9b53c6faeeb1d6fd781acc3a89a4b860b531b55fc3a124cf8f`.
`source-files.expected.json` is copied from the small frozen campaign metadata;
it is not a new runtime hash audit. The unchanged profile is
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

The two scripts write reports to stdout only. They do not seal or publish a
candidate automatically. Keep their real process exit, stdout and stderr in
fresh review artifacts. A successful report is not a critic verdict.

- `verify_campaign_readonly.py.draft` retains the established complete-capture,
  owned-target/helper/Job/wrapper-handle, BoundRun, exact-profile and dataset
  reconstruction checks. It requires named checkpoint proof, all ten fresh
  host/editor pairs, all 35 batches each, and an exact 50-file map. Index 1.3.0
  and startup readiness are required. The existing shared validator additionally
  binds readiness to the original editor snapshot's scene hash, batch0 and
  first READY. Missing/pending/failed or different-closure data is rejected.
- `verify_dependencies_readonly.py.draft` uses the existing S79 process checks
  and S65/S69 repair/readback validators. It compares the seven current backend
  maps (174 files), both UI maps (5 files), all 1,778 recorded S79 raw files,
  the managed replay map (159 files) and its four verifier sources. It checks
  original source copies separately from current dependency projections.

Do not execute either adapter, the checkpoint helper, the S79 verifier, or any
raw-tree inventory while measurement is active. In particular, the old S79
`service-remint-01/verify.py` asserts equality with the broad historical 453-file
live tree and will correctly fail after benchmark-only S80 edits. The new
dependency adapter uses scoped runtime/UI maps and preserves the historical
453 snapshot copies without pretending the whole live tree is unchanged.

After terminal measurement, use the campaign's pinned console Python
`C:/Users/truon/AppData/Local/Programs/Python/Python311/python.exe` with `-B`:

1. Capture actual terminal scheduler status for every launch using the existing
   `studio/tests/replay/campaign_task.ps1 -Command status -CampaignId gt06-s80-campaign-01
   -LaunchNumber N`. Preserve its real command exit/stdout/stderr. The final
   launch must be state3, instances[], result0, with matching task/output/return.
   Collect before task deletion. `return.json` explicitly precedes actual
   supervisor exit and cannot replace scheduler or run ownership proof.
2. Run the unchanged checkpoint helper:
   `zdoc/reviews/20260918-gt06-s71-growth/verify_source_checkpoint.py f75a5d08
   --output NEW/source-git-final.json`.
3. Run the adapted campaign verifier with `--product-root ABS_PRODUCT
   --scheduler-status FINAL_STATUS_JSON --launch-number N
   --source-checkpoint NEW/source-git-final.json`. Save stdout as a fresh
   campaign verification report and retain its actual exit separately.
4. Run the dependency verifier with `--product-root ABS_PRODUCT
   --campaign-verification NEW/campaign-verification.json`. Save stdout/exit
   separately. Neither script invokes a main/run/prepare/repair entrypoint.
5. Build the final review manifest using `collection-recipe.json` and the
   requirements worker's matrix. Explicitly include the source/review/raw maps,
   every supervisor launch, negative evidence and all requested provenance.
   Use the existing inventory pattern in S76 `failure/collect_failure.py`
   (stream SHA256; before/after identity check), not its hard-coded executable
   collector. That collector targets an old failed campaign and must not run
   unchanged. Retain failedattempts in a separate forensic section and never
   append their samples to selected runs.
6. Freeze the manifest's exact bytes; two independent critics must review that
   identical candidate hash and physical raw locator. Reports stay outside the
   candidate to avoid circular hashing. Coordinator acceptance remains separate.

Remaining inputs and risks:

- Terminal campaign/capture/dataset/summary, final scheduler capture and every
  actual supervisor launch's request, claim, expected/registered XML and hash,
  registration, dispatch, start/return/logs, and deletion receipt if applicable.
- Named-commit byte proof and real exits for both offline adapters; neither has
  been executed. Syntax parsing cannot establish that all historical input
  shapes and paths still satisfy these checks.
- Complete selected/unselected raw inventories after terminal; previous S70–S78
  failed campaigns stay separate, under their original source and failure labels.
  Source equality cannot make any failed prefix eligible.
- S79 Stop, saturated Stop and GUI Stop retain missing natural native exit as
  missing/null, with `STAGE_STOPPED` and wrapper2. Outer0 is distinct. Natural
  completion lanes require the actual PID-bound native exit0 and closed/zero
  untainted Jobs. Historical run_fixture owners prove actual target/helper exits
  and empty trees, but do not gain newer capture-v2 handle fields retroactively.
- Preserve S65 fault→authenticated repair02→S65 replay→S69 managed replay
  provenance and accepted GT05 asset bindings. No repair rerun is authorized or
  needed for benchmark-only changes. The dependency script checks the S69
  managed chain; the final raw inventory still includes original S65 replay05.
- The amended S79 REPORT.md now distinguishes source checkpoint `24efe967...`
  from frozen Git HEAD `e4bbc1fe...`, matching `freeze.json`. The older S80
  dependency bridge's discrepancy record describes the earlier report wording;
  it is historical context, not an unresolved error in the current report.
- Current service/index coverage must reference the U79 95-test lane plus S79
  native remints; older U69 service tests do not become current-source tests.
  Preserve U80 focused checks and native startup diagnostic under their own
  scopes and actual exits. Do not sum overlapping test suites.
- Review/governance snapshots, requirements edges, failure/skip ledger, external
  Python/pythonw/Godot pins and any portable view's transformation mappings
  remain final packaging inputs. Portable files have their own hash domain and
  never replace unavailable raw bytes. Generated caches remain out of Git.

The prepared scripts are review candidates. They issue no GT06 verdict and
cannot replace two independent final critics.
