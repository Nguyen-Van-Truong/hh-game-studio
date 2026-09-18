# S90 interruption and phase readback

AUTHORITY=0. This packet verifies a diagnostic prefix, not GT-06 acceptance.

S90 started at 2026-09-18T13:24:30Z through an exec PTY. Its final logs stop at
13:32:44Z, batch 5 native settle. Direct checks at 13:36 and the retained
`liveness-observation.json` found the recorded supervisor, helpers and editor
absent. The exec session was also unavailable. The cause is unknown: process
absence is neither an actual exit code nor proof of Job/handle cleanup.

`manifest.json` retains 183 raw hashes and 128 exact copies under `raw/`.
SHA256: `2b13ade7745f540d0b6601edd92de39d40852533040ec6afdebba4c5c38a54aa`.
No old evidence was overwritten or substituted. Missing terminal receipts stay
missing; no RSS, leak, Stop, or application-cancellation cause is asserted.

`analysis.json` binds five completed warmup pairs (0–4), zero measured pairs and
zero eligible samples. Batch 5 has a bound command/start prefix only. All five
records have publish/preopen/release/fresh ObjectDB=71127, after-close=71128,
resources=6. This proves a constant FileAccess lifetime observation of +1.
It does not explain S86's variable +2: S86's pre-ACK publication already changes
71127 at batch16 to 71129 at batch17, while its ACK changes71128 to71130.

The verifier validates exact helper/native/source hashes, capture references,
phase arithmetic, batch/joint/ACK/start/readiness binding and missing pairs.
Exit 0 means these partial bindings match; it never asserts a complete run or
cleanup. Seventeen offline rejection/regression tests pass; actual process
results and logs are retained in `unit-*` and `analysis-*`.

Reproduce from repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s90-terminal-audit/analyze_lifecycle.py 8-9-hh3d-3/studio/.local/reviews/gt06-s90-lifecycle-attribution-01
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s90-terminal-audit/test_analyze_lifecycle.py
```

Next diagnostic must answer the pre-ACK +2 question. S91 uses a targeted
TreeItem/Node3D census before host baseline sampling, rather than rerunning the
answered FileAccess probe. Its detached scheduler observer retains process
handles independently of the nested Job so forced exits can be observed.
Neither the targeted inventory nor this prefix covers the whole ObjectDB.

The previous HH3D heartbeat was absent when an update was attempted. A single
replacement was created through the app and read back in
`automation-readback.json`; unrelated automations were left alone. This is
automation configuration evidence, not proof that any diagnostic is running.
