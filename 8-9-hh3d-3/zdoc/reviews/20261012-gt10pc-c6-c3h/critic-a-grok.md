TICK=yes

Run `gt10pc-rehearsal-20261012-c3h`. Task closure `86dc9f1cb8fa2e6dc9005d8e4ba2031f4c1862aa930d7287ae9db0077d7724bd` (`c3h-task/request.json`, `return.json`). Package closure `a6280d76c7059d3e1b11aabf6486fe63c00068a19ab8f3c525a569533906da3b` (`matrix.json`). Windows 0.1.0 manifest `3bb561df55ce31b372447be2a9c7bb9e9a8da4c6655f08db176c266db632b595`. Trust `2d19e3e90a719ead39cd1874193f90f98e9f8b2e2b71fb9d0ea451c7336af2e0`. Commit `744a9f61`; `git diff --stat 744a9f61 HEAD -- 8-9-hh3d-3/studio` is empty. `--verify-only` exit 0, status `RAW_VERIFIED`, `errors` {}, no `findings`. Task `return.json` `returned_exit_code` 0 after 1276.5 s; `task-terminal.json` `last_task_result` 0; `formal_acceptance` false.

O14 (plan lines 47–59, checklist 346–347) waives the 10×35 soak and the long final, keeps `REHEARSAL_PASS`, and does not call c3h a soak PASS or a FINAL. Header stays `IN_PROGRESS` until both critics tick. f1–f4 are VOID. That record is honest.

Rows are recomputed from raw, not from the producer PASS string (`gt10pc_matrix_verify.py:116` requires the label, then `verify_raw_rows`). P1 re-scans archive bytes (`:154-158`, `gt10pc_p1_scan.py:48-69`); `release_contract.py:138` rejects `zdoc`/`reviews`. P2 re-runs `verify_package` on the eight attack files (`:164-178`). P3–P6 re-read Windows and Linux host receipts and both fixtures (`:185-193`, `run_gt10pc_matrix.py:729`, `gt10pc_linux_verify.py:40-52`); Play lifecycle is parsed from stdout. P4 refusals are recomputed (`gt10pc_p4_negative.py:201-254`). P7 checks killer pid, victim, tree, second retry, NOT_APPLICABLE reasons, cut selector, and release-tree bytes (`gt10pc_p7_verify.py:98-132`). P8 replays five cases (`gt10pc_p8_checks.py:134-143`). P9 is its own child and checks known-limit terms (`gt10pc_matrix_verify.py:218-226`, `gt10pc_p9_consumer.py:164-165`). P10 binds host pids and applies GT-09 publication, registered, and conformance semantics, and parses both K10 traces (`gt10pc_p10.py:517-524`, `:589-633`). P11 under O14 is the one cycle: child host receipt plus capture (`gt10pc_matrix_verify.py:256-260`).

Pre-review items 1–5 and 7–10, and the 744a9f61 C4b fixes, match this raw: P7 `install-release-renamed/worker-host.json` killer 44912 equals `children/p7-native-a-host.json`; release dir `074f9431…` is the cut selector; `applicability.json` gives reasons; `p9-consumer/.../docs/known-limits.md` names security floor, key lost/leaks, journal, `dynamic_dependencies_verified`, K13, `INCOMPATIBLE`; `p10-linux/.../L01/l01-host.json` pid 10 and `L02/l02-host.json` pid 28, exit 0; arena stdout seed 90127, key 68 held, pause/resume; registered result `readback_ack` true. Item 6 (10×35) is waived by O14.

## BLOCKER

None.

## MAJOR

None.

## MINOR

1. P11 Godot exits are read from `capture.json` `actual_exits` (`run_gt10pc_matrix.py:194-198`), not from `process-exit.json`. Those files agree: import pid 37680 and editor pid 20620, both exit 0 (`gt06-p11-short-ad57e858`). The Python child is bound (`p11-short-host.json` target_pid 5856, exit 0).
2. Native P2 trusts `rejected: true` (`run_gt10pc_matrix.py:424-427`). The eight host attacks are re-executed, and `p2-native/p2.json` before/after install, project, and state hashes are equal.
3. P4 negative cases have no per-case `*-host.json`. Refusals are recomputed. Parent receipts: `children/windows-producer-host.json` pid 7580 and `linux/host/run-host.json` pid 28892, both exit 0. `windows/negative/.../exception.txt` is `unsupported package schema` and `untrusted signing key`.
4. O14.6 names `zdoc/12-10-huong-dan-dung-cong-cu-godot-blender.txt`. That file is not in the tree. The waiver text itself is in the plan.

## UNSURE

The source-drift branch (`gt10pc_matrix_verify.py:117-123`) is not exercised by this matching tree. This package does not show validators running after a mismatched digest.
