# GT04 Blender -02 read-only evidence audit

AUTHORITY=0. ACCEPTANCE=false. PUBLIC_ACK=false. This is a consistency audit
written by the slice implementer, not an independent formal critic signature.
No native engine was launched and no frozen adapter/test/probe source changed.

`verify_probe.py` passes against the actual `20260917-gt04-blender-02` package:
18 Python tests, 27 edit checks, 9 reopen checks, 7 checkpoint checks, exact
28-file artifact inventory. The nine-file source closure remains
`6190abcf73ab5c01e2e5799ed5210179b771a4165f76a430a3275948c729b847`.

The verifier pins all nine current/frozen source hashes and the executable
SHA256; recomputes the closure; extracts only the required-label literal from
the pinned runner via AST (does not execute it); validates actual raw host
PID/exit records against summary records, exact argv, chronology, typed zero
exits, no timeout and historical Job-tree observations; parses raw unittest
completion and every ordered native marker; requires correctly typed flags;
checks separate edit/reopen/checkpoint snapshots and semantic hashes; and
reads actual saved/checkpoint bytes against exact size/hash descriptors.
Inventory membership is fixed, so rehashing an extra artifact cannot admit it.
Only generated `.pyc` files beneath snapshot `source/studio/**/__pycache__` are
excluded, consistently with the capture runner; they are not executable source
authority. The package's incidental compatibility cache remains inventoried.

Ten tests passed, including the actual baseline plus tampered host exit,
Boolean exit code, integer `1` as check pass (both raw and JSON changed),
checkpoint semantic revision, duplicate terminal marker, changed frozen source,
changed `.blend` bytes and extra files. Tests mutate isolated temporary copies;
when appropriate they also recompute artifact hashes to exercise semantic
checks beyond a simple stale inventory. Test and verifier subprocesses each
have a 30-second bound using unchanged `run_fixture.py`; both actual target and
wrapper exits were zero, with `tree_verified=true`. See `capture.json` and
`audit-*-host.json`, stdout and stderr. Audit sources stayed unchanged across
those subprocesses.

Reproduce without Blender:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-blender-audit/verify_probe.py
python -B -m unittest discover -s 8-9-hh3d-3/zdoc/reviews/20260917-gt04-blender-audit -p test_*.py -v
```

Self-review findings and limits:

- **P2, verifier typing:** the frozen original runner at
  `studio/tests/blender/run_blender_probe.py:69–73` compares check dictionaries
  using Python equality, accepting integer `1` where Boolean `True` is
  intended. Its line 59 also allows `False` as the summary wrapper exit.
  The actual capture has the correct types. This external auditor rejects
  those counterexamples; original source is preserved for a future remint.
- **Process proof boundary:** `studio/build/bootstrap/run_fixture.py:207–209`
  ignores `CloseHandle`'s result. The existing runner records an observed zero
  Job process count, not independently checked handle closure. The auditor
  checks the historical records and source that created them; it cannot
  recreate historical live kernel state or authenticate maliciously fabricated
  complete evidence. No extra cleanup/host-death guarantee is inferred.
- **Fixture scope:** `adapter.py:119` hashes its narrow native scene model,
  not every Blender datablock. `blender_probe.py:53` saves only fixed names in
  a fresh exclusive directory, without a GT02 protected owner. The current
  adapter has no UI/IPC, durable dedupe, lease/FIFO, undo/rollback, export,
  material or external-resource closure, hostile-parser sandbox, resource
  quotas or interruption recovery. Autoexec/offline flags are not an OS
  sandbox. These are declared implementation gaps, not passing GT04 criteria.
- **Readback meaning:** fixed saved-byte hashes and separate-process raw
  readback snapshots agree. This read-only auditor does not parse `.blend`
  again and does not claim a new native observation or a public ACK.

The original failed `-01` package is outside this verifier's scope and remains
failed evidence. No commit, checkbox, existing audit, plan, core or Godot
source was changed for this audit.
