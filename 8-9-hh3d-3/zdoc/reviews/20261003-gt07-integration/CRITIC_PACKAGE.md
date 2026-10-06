# GT07 critic package — frozen diagnostic candidate

`AUTHORITY=0` and `FORMAL_ACCEPTANCE=false`. This package is ready to be
handed to two independent read-only critics; the coordinator must not sign it
or infer acceptance from the raw PASS fields.

## Freeze

- Git source freeze: `909d6efe1a1c71af297d9b2ad99fe5a7a666e150`.
- Coordinator manifest: `studio/.local/reviews/gt07-final-matrix-20261006/manifest.json`.
- Manifest SHA-256: `d56845bb130c3038cd63a70f48127f08e55c3a41ab1473d79d180a59c06b1d38`.
- Tracked studio closure: `b7b3a4aeadb8add96681179fa9b4b65fef71b2d13d061fbd825a0495f99d4e28`.
- Commits after the source freeze are recorded in the manifest as docs-only
  drift (`fb7b7b03`, `8549ba34`, `91962245`); no file under `studio/` changed.
- Godot runtime closure: `9a2c41ff1115950f0057530a69098b5a69c8c8c45bc0e851df81891566401193`.
- Blender runtime closure: `17f381a0b2078096d9631556620a4cfd0c5552ad0d49b89865f0234078b7a0e2`.

## Evidence scope

The manifest binds the sequential native Godot/Blender matrix, current M3
producer phase cuts, M7 real-clock rotation suite, M8 process/Job ownership
run, M9 Play-time mutation adversary, and the affected focused regression
suite. Raw evidence stays under `studio/.local/reviews/`; this text is only the
review index. Every native record retains its own dry-run, source closure,
actual child/wrapper exit, Job/tree cleanup and `authority=0` fields.

M9's current-source refresh is recorded separately in
`zdoc/reviews/20261006-gt07-binding-refresh/`; it required the exact prior
metadata hashes and exact three-file delta, and makes no power-loss atomicity
claim across the two metadata replacements.

## Critic instructions

Each critic must read the same manifest and raw receipts without mutation,
verify the source/driver/binary hashes and requirement-to-artifact mapping,
check actual exits and owned cleanup, and write an explicit `TICK=yes` or
`TICK=no` against this exact manifest SHA. Use two different models. A single
critic, a changed source hash, a banner, or a partial prefix cannot authorize
GT07. GT08–GT10 remain separate planned work even if both critics tick GT07.
