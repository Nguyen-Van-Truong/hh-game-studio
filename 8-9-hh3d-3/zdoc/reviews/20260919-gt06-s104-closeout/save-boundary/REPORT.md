# GT06 S104 save-boundary closeout (read-only)

Date: 2026-09-19 (Asia/Saigon)

This report reads the retained raw S103 captures only. It does not launch Godot, mutate the captures, repair the reader, or change formal acceptance.

## Inputs and commands

The exact native source binding used by the markers is `studio/tests/replay/benchmark_native.gd` (SHA-256 `13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`). The generated overlay copies in each S103 disposable project hash `bb137f32f1fae3730cc139f03fc6902813b3742d5a08d437e957e291cfe0ec46`; passing an overlay copy as `--native-source` correctly failed closed because its bytes do not match the marker's `probe_source_sha256`.

Commands run (from `8-9-hh3d-3`; no engine process was started):

```powershell
python -B zdoc/reviews/20260919-gt06-s103-status-gap/read_native_save.py --stdout studio/.local/reviews/gt06-s103-prefix-preflight-06/editor-host/stdout.txt --native-source studio/tests/replay/benchmark_native.gd --batch studio/.local/reviews/gt06-s103-prefix-preflight-06/project/benchmark/out/batch-00.json --lifecycle studio/.local/reviews/gt06-s103-prefix-preflight-06/editor-host/cleanup-001.json --binding studio/.local/reviews/gt06-s103-prefix-preflight-06/context.json
python -B zdoc/reviews/20260919-gt06-s103-status-gap/read_native_save.py --stdout studio/.local/reviews/gt06-s103-prefix-01/editor-host/stdout.txt --native-source studio/tests/replay/benchmark_native.gd --batch studio/.local/reviews/gt06-s103-prefix-01/project/benchmark/out/batch-00.json --batch studio/.local/reviews/gt06-s103-prefix-01/project/benchmark/out/batch-01.json --batch studio/.local/reviews/gt06-s103-prefix-01/project/benchmark/out/batch-02.json --batch studio/.local/reviews/gt06-s103-prefix-01/project/benchmark/out/batch-03.json --batch studio/.local/reviews/gt06-s103-prefix-01/project/benchmark/out/batch-04.json --batch studio/.local/reviews/gt06-s103-prefix-01/project/benchmark/out/batch-05.json --lifecycle studio/.local/reviews/gt06-s103-prefix-01/editor-host/cleanup-001.json --binding studio/.local/reviews/gt06-s103-prefix-01/context.json
```

Both commands exited `2` with `frame boundary order`. Their raw stdout, batch JSON, run/profile/source bindings, and lifecycle receipts were retained unchanged. Full input sizes and SHA-256 values are in `input-hashes.json`; the reader itself is `read_native_save.py` SHA-256 `a332fd257e9253141ffd63862eb8a73cb1ad655333e104bfc8845f8969ac3817`.

## Boundary result

A separate derived read-only pass (`analyze_boundary.py`, output `derived-boundary.jsonl`) parsed the same bytes without changing them. It confirms:

| run | enter markers | complete markers | complete records with all call/signal/frame/readback fields and valid bindings | longest `save_scene` call | longest call→next process entry | longest gap after save-process exit to next process entry |
|---|---:|---:|---:|---:|---:|---:|
| `gt06-s103-prefix-preflight-06` | 100 | 100 | 100 | 365.616 ms | 370.027 ms | 25.514 ms |
| `gt06-s103-prefix-01` | 600 | 600 | 600 | 434.406 ms | 439.206 ms | 27.110 ms |

All complete records have `failed=false`, `observation_complete=true`, `save_result=0`, matching `run_id`/PID/cycle/sequence/source/profile, and matching the bound native source hash. No observed interval crossed the reader's 2,000 ms threshold. The frame progression is consistently `process_entry_frame < save_process_exit_frame < next_process_entry_frame = next_process_exit_frame` (for example 5698, 5703, 5704, 5704).

## Reader limitation

`read_native_save.py` line 270 requires `process_entry_frame == save_process_exit_frame`. The emitted records legitimately advance the frame during the save dispatch, so this equality rejects every otherwise complete record. This is a reader bug/contract mismatch, not a raw-data repair and not a PASS. The reader therefore reports `UNKNOWN` for both runs despite 100/600 complete boundary records in the derived audit. The lifecycle receipts are diagnostic forced stops (`BENCHMARK_CLOSED_BEFORE_FINISH`); no natural target exit is claimed.

The retained S103 summary's prefix gap correction is confirmed: the maximum prefix gap is **728.622 ms** (batch 1), while measured batch 5 is **642.433 ms**. These are separate values.

## Next step and limits

Keep both runs excluded from F13/F14 and formal acceptance. The next narrow action is to review and correct the reader's frame-order predicate (or explicitly record a versioned predicate that permits the observed progression), then rerun this reader read-only against the same hashes. Do not infer disk, scheduler, renderer, leak identity, or engine causality from these timings; no PASS or root cause is established.
