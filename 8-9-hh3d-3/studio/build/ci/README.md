# GT-08A clean import/export matrix

`gt08a_matrix.py` is the single producer and verifier for the public GT-08A
slice. It is scoped to `studio/build/ci/` and does not mutate a game project,
the global Godot cache, PATH, Docker, or the pinned toolchain. It records
actual process exits and hashes in `studio/.local/reviews/<run_id>/`, which is
ignored and must remain immutable after a run.

Run the admission first:

```text
python studio/build/ci/gt08a_matrix.py --dry-run
```

The dry-run validates the 18-row O10.9 table, complete fixture closure,
Godot/template pins, target-aware cache keys, and the local test signer. It
must report `engine_launched=false` and `network_used=false`.

After reviewing that output, run exactly one final matrix with a new ID:

```text
python studio/build/ci/gt08a_matrix.py --matrix \
  --run-id gt08a-matrix-YYYYMMDD-NN
```

The runner copies the fixture to a path containing Unicode and spaces, stages
only the locked Windows/Linux export templates under its private user root,
performs Windows import/export, and checks Linux headless import/export via
WSL when available. A missing target, wrong template, changed source, failed
exit, timeout, or dirty owned process is a failure; no banner is treated as a
pass. The Android target is intentionally outside GT-08A and remains the
GT-08B physical-device gate.
