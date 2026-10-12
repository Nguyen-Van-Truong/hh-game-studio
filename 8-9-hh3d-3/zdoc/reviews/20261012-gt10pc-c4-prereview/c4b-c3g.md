# GT-10-PC C4b read-only audit of rehearsal c3g

Judged the ten BLOCKER/MAJOR items in `8-9-hh3d-3/zdoc/reviews/20261012-gt10pc-c4-prereview/prereview.md` against the working tree and `8-9-hh3d-3/studio/.local/reviews/gt10pc-rehearsal-20261012-c3g`. No Python, Godot, Docker, hash of `.hhpkg`, or file under `8-9-hh3d-3` was written. `private.raw` was not opened.

Evidence root below is `8-9-hh3d-3/studio/.local/reviews/gt10pc-rehearsal-20261012-c3g`.

## Gap items

### 1. BLOCKER — recompute every row from raw
- Verdict: FIXED
- Code: `8-9-hh3d-3/studio/tests/conformance/gt10pc_matrix_verify.py:127-269` (`verify_raw_rows` opens archives, P2 attack bytes, `verify_linux`, `verify_p7`, `verify_p8`, `verify_consumer`, `verify` for P10, and the P11 short or 10×35 reader). Linux docker host: `gt10pc_linux_verify.py:40-52` requires `host/run-host.json` and `_process` binds `target_pid`/`exit_code` (`run_gt10pc_matrix.py:640-648`). `--verify-only` calls that reader (`run_gt10pc_matrix.py:851-861`).
- Evidence: `linux/host/run-host.json` (`target_pid` 19136, `exit_code` 0); `children/windows-producer-host.json` (`target_pid` 39116); `p7-native-a/cases/install-release-renamed/worker-host.json`; `p10-gt08a/gt08a/W02/w02-host.json`; `p10-linux/linux/native/k10/gt09-arena/godot-stdout.txt`; `p11-short-child/p11-short-host.json`.
- Reason: Rehearsal verify no longer accepts a row from `REHEARSAL_PASS` alone; each c3g row above is re-read from those raw files (final campaign receipts are the separate item 6 path and are not in this rehearsal).

### 2. BLOCKER — P1 member-byte monetization and failpoint scan
- Verdict: FIXED
- Code: `8-9-hh3d-3/studio/tests/conformance/gt10pc_p1_scan.py:48-69` scans every zip member for payment/monetization tokens and an armed failpoint and fail-closes; `gt10pc_matrix_verify.py:154-158` recomputes `scan_archive` and requires equality with `rows.P1.scans`.
- Evidence: `matrix.json` lines 37-89 (`schema` `hh-gt10pc-p1-scan-2`, `payment_members` 0, `monetization_members` 0, `armed_failpoints` 0 on all four archives) and the four archives named in `matrix.json` `artifacts`.
- Reason: Admission is a recomputed member-byte scan, not the builder-written manifest flags.

### 3. BLOCKER — P8 missing dependency, missing template, addon mismatch
- Verdict: FIXED
- Code: `run_gt10pc_matrix.py:123-128` calls `run_p8`; `gt10pc_matrix_verify.py:212-217` calls `verify_p8`; `gt10pc_p8_checks.py:20` lists `missing-dependency`, `missing-template`, `addon-version`, `archive`, `closure`, and `verify_p8` (`gt10pc_p8_checks.py:116-146`) replays each case against `observation.json`.
- Evidence: `p8-host/missing-template/observation.json` (export-templates rejection, `install_absent` true) and `p8-host/addon-version/observation.json` (addon version mismatch, addon unchanged).
- Reason: The five observation directories exist and the verifier replays them instead of checking only a missing Godot path and a package version.

### 4. BLOCKER — P7 per-case kill receipt, last-good, second retry, addon bytes, NOT_APPLICABLE
- Verdict: NOT_FIXED
- Code: Killer/victim/tree/exit, second retry, addon bytes, and NOT_APPLICABLE are enforced at `gt10pc_p7_verify.py:80-106` and `114-164` (killer pid must equal the group host `target_pid`). Last-good is only `digest_file(install-before-reopen.json) == row["install_before_reopen_sha256"]` (`gt10pc_p7_verify.py:107-109`). The writer copies `.install.json` bytes (`run_gt10pc_p7.py:332-339`) and never hashes both release trees; the verifier does not recompute `state_digest` on that snapshot.
- Evidence: eight `worker-host.json` files (schema `hh-gt10pc-p7-worker-host-2`; group killer pids 20872, 27272, 14684 match `children/p7-native-{a,b,c}-host.json`); eight `applicability.json`, `retry-proof.json`, and `project-final.json` files; `p7-native-a/cases/install-release-renamed/install-before-reopen.json` is the install journal (`schema` `hh-studio-install-4`), not a release-tree hash ledger. One sampled `retry-proof.json` has `first==second` and equal install, project, and state before/after the second retry.
- Reason: Four of the five clauses are enforced from raw files, but last-good hashes of the release trees right after the cut are not recomputed, so a producer-written journal hash is enough to pass.

### 5. BLOCKER — P10 L01/L02, W02/W03 host pids, K10 trace
- Verdict: FIXED
- Code: `gt10pc_p10.py:594-600` requires `W02`/`W03` `*-host.json` pids; `gt10pc_p10.py:512-536` requires L01/L02 host pids, `--max-fps 60`, and `verify_k10_trace` (`gt10pc_p10.py:182-229`) on both fixture stdout files (pressed/released, held key 68, seed 90127, pause/resume).
- Evidence: `p10-gt08a/gt08a/W02/w02-host.json` pid 42560 and `W03/w03-host.json` pid 25700, both exit 0; `p10-linux/linux/native/gt08a/L01/l01-host.json` pid 11 and `L02/l02-host.json` pid 29; `p10-linux/linux/host/run-host.json` pid 19588 (Windows docker client); `p10-linux/linux/native/k10/gt09-arena/godot-stdout.txt` and `gt09-room/godot-stdout.txt` (seed 90127, key 68 held, key 69, pause/resume) with `godot-host.json` pids 274 and 284.
- Reason: Windows import/export and Linux headless import/export have host pid receipts, and both fixtures have a 60 Hz pressed/held/released trace that the verifier parses.

### 6. BLOCKER — P11 10×35 final, drop 2×35 checker, bind campaign and short-child receipts
- Verdict: UNCLEAR
- Code: `_p11_full_final` (`run_gt10pc_matrix.py:277-333`) runs five frozen 2×35 campaigns and labels `formal-10x35` (10 pairs, 350 batches, measured 300/300000/30000). `_verify_p11_10x35` (`gt10pc_matrix_verify.py:18-100`) re-reads each campaign receipt, capture, dataset, and `verify_run_capture`, which requires `process-exit.json` and exit/job gates (`run_benchmark_campaign.py:1168-1188`) plus the O1.4 memory gates inside `validate_dataset`. No `formal-2x35` or `_verify_p11_final_row` remains. The rehearsal branch binds `p11-short-host.json` (`gt10pc_matrix_verify.py:256-260`).
- Evidence: `p11-short-child/p11-short-host.json` and `p11-short-receipt.json` both record `target_pid` 31460 and `exit_code` 0; `matrix.json` row P11 is `coverage` `one-real-Godot-cycle`. There is no `campaign-receipts/` directory in c3g.
- Reason: The final 10×35 checker is in the source and the short child is bound, but this rehearsal has no five-campaign raw receipt to show that the 10×35 path was exercised.

### 7. MAJOR — P4 incompatible schema and untrusted rollback, with host receipts
- Verdict: NOT_FIXED
- Code: `verify_negative` (`gt10pc_p4_negative.py:201-271`) recomputes both refusals from the package bytes, exception text, and unchanged install state. It is called for Windows (`run_gt10pc_matrix.py:842-845`) and Linux (`gt10pc_linux_verify.py:181-188`). It never reads a `target_pid` or `exit_code`.
- Evidence: `windows/negative/incompatible-schema/exception.txt` is `unsupported package schema` and `windows/negative/untrusted-rollback/exception.txt` is `untrusted signing key`; the same two texts are under `linux/native/negative/`. Neither case directory contains a `*-host.json`.
- Reason: Both platforms record the two refusals and the verifier recomputes them, but there is no per-case host pid/exit receipt.

### 8. MAJOR — `--verify-only` continues after source drift
- Verdict: UNCLEAR
- Code: `gt10pc_matrix_verify.py:117-124` runs `verify_raw_rows` before comparing digests, then sets finding `SOURCE_DRIFT` and status `DIAGNOSTIC_SOURCE_DRIFT`. `run_gt10pc_matrix.py:859-861` prints that object and returns 2 unless status is `RAW_VERIFIED`, so a drifted verify does not return on `REHEARSAL_PASS` or `FINAL_PASS`.
- Evidence: c3g `matrix.json` `source_closure_sha256` is `9fa3674464ae6e9982fd6d169d69594fb79c6aca5f857f563bd17ed5abd5605a` and `status` is the producer `REHEARSAL_PASS`. No c3g or c3g-task file records a `DIAGNOSTIC_SOURCE_DRIFT` result.
- Reason: The drift branch is implemented, but this passing rehearsal does not contain a raw diagnostic that shows validators ran after a mismatched digest.

### 9. MAJOR — P9 consumer is its own child
- Verdict: FIXED
- Code: `run_gt10pc_matrix.py:550-557` launches `gt10pc_p9_consumer.py` through `_child`; `gt10pc_matrix_verify.py:218-226` requires `children/p9-consumer-receipt.json` and `_process` on that host file, then `verify_consumer`.
- Evidence: `children/p9-consumer-host.json` (`target_pid` 31004, `exit_code` 0) matches the receipt embedded in `matrix.json` row P9.
- Reason: The consumer is a separate host child with a pid/exit receipt, not an in-process call.

### 10. MAJOR — known limits name security floor and key-loss recovery
- Verdict: FIXED
- Code: `8-9-hh3d-3/studio/package/known-limits.md:7-12` states the fixed `local-test-floor-1` floor and recovery when the pinned test key is lost or leaks, next to rotation/revocation/expiry at lines 3-4.
- Evidence: `p9-consumer/install/releases/bd9cccd2f9bb0d27fece7f1b8d5e721bd00239064f09e01e0bbf5c5dea40bced/docs/known-limits.md` contains the same sentences.
- Reason: The installed package document, not only the source file, names both deferred limits.

## NEW FINDINGS

### N1. MAJOR — catalog child receipts are not bound to host pid files
`gt10pc_p10.py:130-139` (`_verify_child_receipt`) checks exit flags on the receipt object stored in `p10.json` and rehashes stdout/stderr. It does not open `p10-catalog/children/*-host.json` or require that file's `target_pid`. `gt10pc_p10.py:622-636` still accepts registered and publication `status == DIAGNOSTIC_PASS` (and `native_process.exit_code == 0`) without re-reading `readback_ack` or the command-id list. Those host files exist (`blender-content-host.json`, `registered-arena-host.json`, `registered-room-host.json`, `publication-arena-host.json`, `publication-room-host.json`, `k10-conformance-host.json`).

### N2. MAJOR — P11 short Godot exits are taken from capture.json
`run_gt10pc_matrix.py:194-203` accepts import/editor pid and exit from `capture.json` `actual_exits` and does not open `process-exit.json`. The files exist and agree (import pid 42500, editor pid 24020, both exit 0) at `8-9-hh3d-3/studio/.local/reviews/gt06-p11-short-ee566901/import-host/process-exit.json` and `editor-host/process-exit.json`, but a substituted capture would still pass. The Python child host pid is bound (item 6); these two Godot exits are not.

### N3. MAJOR — known-limits sentences are not enforced
`gt10pc_p9_consumer.py:159-160` only requires `docs/known-limits.md` to be non-empty. Removing the security-floor and key-loss sentences would still satisfy the verifier. The current c3g copy does contain them (item 10).

## Counts

FIXED 6 (items 1, 2, 3, 5, 9, 10). NOT_FIXED 2 (items 4, 7). UNCLEAR 2 (items 6, 8). New MAJOR findings: N1, N2, N3.
