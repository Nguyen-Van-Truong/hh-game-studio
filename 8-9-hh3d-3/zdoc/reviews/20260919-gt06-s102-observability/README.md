# S102 observability integration preflight

Coordinator completed run-01: import target30408 exit0, host24852/helper23568
exit0, 20 HTTP commands, checked cleanup, zero stderr and unchanged pins.
Import took5.016s with52 samples; maximum command status gap54.4386ms.
`AUTHORITY=0`; all outputs remain supplemental, `formal_acceptance=false`,
and excluded from the performance dataset. See `coordinator-validation.md`.

These commands document the completed invocation; do not rerun `--launch`
over the existing `run-01`:

```powershell
& 'C:/Users/truon/AppData/Local/Programs/Python/Python311/python.exe' -B '8-9-hh3d-3/zdoc/reviews/20260919-gt06-s102-observability/preflight.py' --check
& 'C:/Users/truon/AppData/Local/Programs/Python/Python311/python.exe' -B '8-9-hh3d-3/zdoc/reviews/20260919-gt06-s102-observability/preflight.py' --launch
```

`--check` compiles this helper, imports the campaign, calls `load_fixture()` and
checks the expected 53-file formal source map, original profile, native 20-second
limit, validators and pinned Godot executable. It does not construct a producer,
open HTTP listeners, run an engine or create evidence files.

`--launch` exclusively creates `run-01`; existing output is rejected. It copies
the complete current formal closure and this helper, binds profile/Python/Godot
hashes, rechecks source before release, and owns the copied child with the
existing `BenchmarkProcess(campaign_host=True)`. Its execution map additionally
binds the helper, freeze manifest and immutable child context. Source changes
during or after freezing invalidate the result. No formal source, profile,
accepted core, command report schema or production owner limit is modified.

The child prepares the full-bound fixture using `campaign.prepare`, runs exactly
one `campaign._observed_import` with the native stage's original 20-second cap
and `ImportObserver`, then runs two original `CommandProducer.run_diagnostic()`
groups of ten mix commands each. Cancel/setup/lookup traffic remains inherited.
It launches no editor benchmark and executes zero native benchmark cycles.

Producer and import-observer cleanup are independent. HTTP observation is written
with `campaign._write_observation` after cleanup, with the original command report
schema 1.3.0 retained in separate files. The child and parent both call
`verify_observations`; the parent joins HTTP PID to the actual owned child exit,
and the import joins to its own actual process-start/process-exit receipts.
Original exceptions, partial command reports, cleanup errors and missing exit
receipts remain explicit; a zero Job never supplies a missing natural exit.

The harness allows 75 seconds from launch entry through child execution, leaving
normal bounded cleanup within a roughly 90-second outer target. It polls the
existing owner and terminates only the owned Job on expiry. Cleanup must still
complete and be recorded; an OS-blocked cleanup is a gap, never a claimed hard
90-second success or a reason to change the native 20-second cap.

Primary outputs are `run-01/freeze.json`, `execution-source-files.json`,
`owned/capture.json` (only for independently verified natural success),
`child/import-host/*`, `child/import-observation.json`,
`child/http-phases-final.json`, `child/command-00.json`, `child/command-01.json`,
`child/report.json`, and `run-01/result.json`. Captured helper/target exits,
Job state, released process/probe handles, source hashes and validators are
required for the preflight to return zero. No output is overwritten.
