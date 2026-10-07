# GT07 critic package — superseded diagnostic candidate

`AUTHORITY=0` and `FORMAL_ACCEPTANCE=false`. This historical package is **not
ready for critic handoff**. Its freeze predates the ordered 17-row admission
and later source changes, so it must not be reused, cited as the current
candidate, or treated as a pending approval request. A new package may be
created only after F3 is complete, one fresh source freeze is bound to the
complete matrix, and all actual exits and cleanup receipts are present.

## Supersession record

Superseded on 2026-10-06 by the runner/admission work recorded in
`requirements.md`. The old manifest SHA below remains immutable historical
provenance only. No critic was requested for this package and no acceptance
may be inferred from any raw PASS field.

## Freeze

- Git source freeze: `909d6efe1a1c71af297d9b2ad99fe5a7a666e150`.
- Coordinator manifest: `studio/.local/reviews/gt07-final-matrix-20261006/manifest.json`.
- Manifest SHA-256: `5f34c0a616c27070779344e65800f9d353666dfab81ae46e1789a7be303bce0d`.
- Tracked studio closure: `b7b3a4aeadb8add96681179fa9b4b65fef71b2d13d061fbd825a0495f99d4e28`.
- Commits after the source freeze are recorded in the manifest as docs-only
  drift (`fb7b7b03`, `8549ba34`, `91962245`); no file under `studio/` changed.
- Godot runtime closure: `9a2c41ff1115950f0057530a69098b5a69c8c8c45bc0e851df81891566401193`.
- Blender runtime closure: `17f381a0b2078096d9631556620a4cfd0c5552ad0d49b89865f0234078b7a0e2`.

## Evidence scope

The manifest binds the sequential native Godot/Blender matrix, current M3 producer phase cuts (including the fresh PREPARED cut gt07-native-queue-20261006-19) and current-source consumer cuts gt07-cross-app-20261006-02 (RELOAD) and -03 (ACK), M7 real-clock rotation suite, M8 process/Job ownership run, M9 Play-time mutation adversary, M1/M5/M6 hash-bound receipts, and the recorded affected focused regression suite. Raw evidence stays under `studio/.local/reviews/`; this text is only the
review index. Every native record retains its own dry-run, source closure,
actual child/wrapper exit, Job/tree cleanup and `authority=0` fields.

Historical M3 consumer cuts gt07-cross-app-20261005-53 and -54 remain retained as contextual provenance. The current-source consumer cuts are gt07-cross-app-20261006-02 (RELOAD: HELD_LAST_GOOD) and -03 (ACK: COMMITTED_LOOKUP_ONLY), both closure-bound and with actual failpoint/recovery exits and clean Jobs. The current M5 host report gt07-m5-storage-20261006-01 is closure-bound to source file 9547c4ef… and has an explicit terminal receipt; injected fsync/diskfull rows remain UNKNOWN. M1/M6 and the completed 104-test regression summary are path/hash-bound in the manifest evidence map.

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
