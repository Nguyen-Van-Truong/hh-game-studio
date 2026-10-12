TICK=yes

## Package checked

- Run: `gt10pc-rehearsal-20261012-c3h`
- Freeze commit: `744a9f61`. `git diff --stat 744a9f61 HEAD -- 8-9-hh3d-3/studio` is empty.
- Later commits also change `8-9-hh3d-3/AGENTS.md`, the tools plan, and `zdoc/reviews/20261012-gt10pc-c4-prereview/c4b-c3g.md`. None of those are studio payload.
- Task studio-tree closure (request.json and return.json): `86dc9f1cb8fa2e6dc9005d8e4ba2031f4c1862aa930d7287ae9db0077d7724bd`. That hash is the supervisor wrapper of the payload digest plus `gt10pc_signing.py` (`studio/tests/replay/run_gt10pc_task.py:48-54`).
- Package / matrix / release-manifest source closure: `a6280d76c7059d3e1b11aabf6486fe63c00068a19ab8f3c525a569533906da3b` (`matrix.json` artifacts and line 758).
- Windows 0.1.0 manifest sha256: `3bb561df55ce31b372447be2a9c7bb9e9a8da4c6655f08db176c266db632b595`.
- Trust store sha256 passed to the verifier: `2d19e3e90a719ead39cd1874193f90f98e9f8b2e2b71fb9d0ea451c7336af2e0`.
- Scheduled Task `\HHStudio.GT10PC.gt10pc-rehearsal-20261012-c3h`: `returned_exit_code` 0, `elapsed_seconds` 1276.484, `actual_process_exit_observed` true, `formal_acceptance` false. `task-terminal.json` `last_task_result` 0. `task-deleted.json` present. Task stderr length 0.
- `matrix.json`: `schema` `hh-gt10pc-matrix-3`, `mode` REHEARSAL, `authority` 0, `acceptance` false, `status` REHEARSAL_PASS, rows P1–P11. Not a FINAL package.

## Verifier observed

Command: `python -B studio/tests/conformance/run_gt10pc_matrix.py --verify-only` on this run with the trust path and trust sha256 above.

- Process exit: 0
- `status`: `RAW_VERIFIED`
- `errors`: `{}`
- No `findings` key (that key is set only for `SOURCE_DRIFT` at `gt10pc_matrix_verify.py:121-123`)
- `acceptance` false, `authority` 0, `mode` REHEARSAL. Those labels are the O14 rehearsal labels, not a soak or FINAL claim.

`verify_matrix` still requires each producer row status to be `REHEARSAL_PASS` (`gt10pc_matrix_verify.py:116`) and then `verify_raw_rows` recomputes the rows from files. A drifted studio payload would have been `DIAGNOSTIC_SOURCE_DRIFT` with exit 2 (`gt10pc_matrix_verify.py:118-123`, `run_gt10pc_matrix.py:859-861`). This run did not drift.

## O14 honesty

Plan O14 (`8-9-godot-blender-agent-studio-plan.txt:47-63`) waives the 10×35 soak and the long final, names this rehearsal as the package, keeps `REHEARSAL_PASS`, and says not to call it FINAL or a soak PASS. The header (`:5`) and status row (`:35`) still say GT-10-PC is in progress pending two critics. `matrix.json` does not say FINAL_PASS. Known-limit text in O14.3 matches the waiver: long-session leak measurement is not claimed.

## Pre-review items and C4b fixes

1. Row recompute: `verify_raw_rows` (`gt10pc_matrix_verify.py:152-265`) re-reads archives, attack bytes, Linux/Windows producers, P7, P8, the P9 child, P10, and the P11 short child. It does not copy producer PASS strings into the result.
2. P1 member scan: `scan_archive` (`gt10pc_p1_scan.py:48-69`) reads every zip member for payment, monetization, and an armed failpoint. The verifier requires equality with `rows.P1.scans` (`gt10pc_matrix_verify.py:156-158`). Observed four archives, schema `hh-gt10pc-p1-scan-2`, 809 members, payment/monetization/armed counts 0.
3. P8: five cases `missing-dependency`, `missing-template`, `addon-version`, `archive`, `closure` (`gt10pc_p8_checks.py:20`). `verify_p8` (`:116-146`) replays each case against `observation.json`. Directories exist under `p8-host/`.
4. P7: eight cases across `p7-native-a/b/c` (3+3+2). `verify_p7` binds killer pid to the group host (`gt10pc_p7_verify.py:109-111`), victim pid to `cut.json` (`:100`), non-zero exit only for kill (`:101`), second-retry ledger equality (`:137-144`), addon bytes (`:174-187`), and NOT_APPLICABLE reasons (`:112-117`). Spot-check: group hosts 44912, 9076, 16784; `install-release-renamed` killer 44912, victim 8320, exit 1, cut pid 8320; `rollback-stop-before-selector` killer 16784, victim 19128, exit 0. Applicability reasons name local WAL and no session token. C4b selector/last-good fix is present (`:28-36`, `:121-132`): snapshot `active` `074f943198679b51b41176053dfdb219655d73abd40f8917b2e9fddd15102c6c` is a release directory under that case, schema `hh-studio-install-4`.
5. P10: L01 host pid 10 exit 0, L02 host pid 28 exit 0, container `run-host.json` pid 1284 exit 0 (`gt10pc_p10.py:503-524`). W02 pid 9360, W03 pid 34192, both exit 0. K10 arena pid 273 and room pid 283, both exit 0. Arena stdout has seed 90127, held key 68, pause at wall_tick 40 and resume at 52 with the same world position. C4b K8/K10 fix calls `_publication_semantics`, `_registered_semantics`, and `_conformance_semantics` and binds catalog `*-host.json` (`gt10pc_p10.py:589-631`). Arena registered result has `readback_ack` true and profile `hh-godot-gameplay-source-1`. Registered-arena host pid 29004, publication-arena host pid 37044, both exit 0. `k10-conformance.json` status is `CANDIDATE_PASS`.
6. P11 10×35 is waived by O14. The short path binds `p11-short-host.json` (`gt10pc_matrix_verify.py:256-260`). Observed target_pid 5856, exit_code 0. Capture `gt06-p11-short-ad57e858` profile `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`, `full_benchmark` false, `formal_acceptance` false. Import `process-exit.json` pid 37680 exit 0 and editor pid 20620 exit 0 match `capture.json` `actual_exits`.
7. P4 negatives ran on both platforms. Windows and Linux `exception.txt` are `unsupported package schema` and `untrusted signing key`. `verify_negative` (`gt10pc_p4_negative.py:201-271`) recomputes both refusals from the package bytes and unchanged selectors. Verifier result `P4_NEG_VERIFIED` on both sides.
8. Source-drift continuation is implemented (`gt10pc_matrix_verify.py:117-123`). This matching tree correctly did not take that branch.
9. P9 consumer is its own child. `p9-consumer-host.json` target_pid 40832 exit 0 matches the matrix child. `verify_consumer` checks the ledger, Godot host, and support allowlist (`gt10pc_p9_consumer.py:85-168`).
10. Installed `p9-consumer/.../docs/known-limits.md` names the security floor, lost key, journal, `dynamic_dependencies_verified`, and K13 `INCOMPATIBLE`. `KNOWN_LIMIT_TERMS` (`gt10pc_p9_consumer.py:24-26`) is enforced at `:164-165`.

Other checklist rows: P2 host attacks are recomputed by re-reading mutated bytes and calling `verify_package` (`gt10pc_matrix_verify.py:160-178`). The native rejection child is pid 43928 exit 0; install/project/state before and after are required equal (`run_gt10pc_matrix.py:419-423`). `ConsumerInstall.install` verifies before staging (`consumer_install.py:252-261`). Windows producer host pid 7580 exit 0. Linux docker `run-host.json` pid 28892 exit 0. Both fixtures are in the Windows and Linux lifecycle results, including upgrade and rollback Play.

## Findings

### BLOCKER

None.

### MAJOR

None.

### MINOR

1. P4 case directories have no per-case `*-host.json`, and `verify_negative` never reads `target_pid` (`gt10pc_p4_negative.py:201-271`). The refusals are in-process inside the Windows producer (pid 7580) and the Linux `docker run` (pid 28892). Both refusals are still recomputed from raw package bytes and unchanged selectors.
2. `_verify_p11_short_row` takes import/editor pid and exit from `capture.json` `actual_exits` (`run_gt10pc_matrix.py:194-198`) and does not open `process-exit.json`. Those files agree with the capture on this run (37680/0 and 20620/0). The Python child host receipt is bound.
3. Native P2 trusts `rejected: true` on `p2.json` (`run_gt10pc_matrix.py:424-427`). Ledger equality and the child host receipt are recomputed. The eight archive attacks are recomputed separately.
4. P1 scan does not reject `zdoc` or `reviews` path segments (`gt10pc_p1_scan.py:48-69`). Payment, monetization, and armed-failpoint scans are recomputed and empty.
5. Windows Play phases are install, upgrade, and rollback (`run_gt10pc_matrix.py:812`). Reinstall is a receipt plus ledger check, not another Play. The Linux result includes a reinstall phase with lifecycle 8.

## UNSURE

- Zip member names were not listed here, so absence of a `zdoc` or `reviews` path inside the four archives was not independently confirmed. The recomputed member-byte scan reported 809 members and zero payment, monetization, and armed-failpoint hits.
- P11 row `source_closure_sha256` `db7f28a40bcdec5948e356bfd60ac08864e580aa4573683686e7eed5d4e237a2` is the benchmark binding inside `capture.json`, not the package closure `a6280d76…`. The short command is the live `run_native_benchmark.py`, and the short verifier does not equate the two hashes. Under O14 this cycle is the accepted one-cycle Godot run, not the waived release soak. The benchmark closure was not recomputed from `source-files.json` in this review.
