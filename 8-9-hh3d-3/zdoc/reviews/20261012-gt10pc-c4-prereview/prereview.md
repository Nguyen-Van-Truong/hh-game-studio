# GT-10-PC C4 pre-review on rehearsal c3e (12-10-2026)

Reviewer: owner's O13 reviewer (Claude), with four read-only helper audits (Grok 4.7 xhigh) in
`detail-*.md`. The severity list below is the reviewer's decision; helper files hold paths and
line numbers and were spot-checked for P8, P10 and the monetization rule. This is a gap list
(O13.3h), not a TICK. Package: `studio/.local/reviews/gt10pc-rehearsal-20261012-c3e`
(REHEARSAL_PASS P1–P11, 1640 s, produced by HEAD d9a13d22). Agent WIP at 08:57 was read only to
mark items already being fixed.

## BLOCKER — a final with any of these is not acceptable

1. Every row verdict must be recomputed from raw in rehearsal, final and --verify-only. HEAD
   accepts P1–P11 from producer status strings. WIP `verify_raw_rows` re-opens P1 archives, P2
   attack bytes and ledgers, P3–P6 producer and Linux, P9 consumer. Still missing: P7 case files
   (`cut.json`, `worker-host.json`, the command row), P10 GT-08A rows and K10 trace, P11 campaign
   receipts, and `linux/host/run-host.json` (docker CLI pid/exit) as the Linux host receipt.
2. P1 artifact scan: monetization and failpoint come from builder-written manifest flags. The
   spec requires `MONETIZATION_POLICY=OFF_ARTIFACT_SCAN_REQUIRED` (plan GT-10 spec, about line
   1460): scan member bytes of each `.hhpkg` for payment SDK, endpoint, voucher, refund,
   chargeback handler or monetization UI, and for an armed failpoint; fail closed.
3. P8 full checker: HEAD checks only a missing dependency and a package version. Missing
   template and addon version mismatch are absent and c3e has no `p8-host/`. WIP calls
   `gt10pc_p8_checks.run_p8`; the verifier must call `verify_p8` on the observation dirs.
4. P7 per case: host-recorded killer PID, victim PID and process tree, exit; last-good hashes
   taken right after the cut and before reopen; a second retry with the same command_id leaves
   install, project and state unchanged; restored addon matches the selected release hashes
   (WIP adds this for schema -2); network loss and token rotation recorded NOT_APPLICABLE with a
   reason (local WAL, no network client, no session token), as the DoD requires.
5. P10: GT-08A Linux headless import/export rows (L01, L02) did not run (`gt08a.json` has only
   W01–W03); W02/W03 have no host PID receipt; K10 on the installed copy lacks the 60 Hz
   pressed/held/released trace with seed and pause/resume (arena has no `input_trace_ok`).
6. P11: final must be 10 fresh host/editor pair × 35 batch (O1.6) with the O1.4–O1.5 gates.
   HEAD wires the GT-06 benchmark 2×35. WIP runs five 2-pair campaigns but still contains a
   2×35 final-row verifier; remove it and bind each campaign's host receipt (process-exit,
   capture) in the verifier, including the short rehearsal child `p11-short-child`.

## MAJOR — fix before the final

7. P4 negative paths on both platforms: an incompatible schema is rejected (or a reviewed
   migration runs) and a rollback to an untrusted or incompatible release is refused, each with
   host receipts. 0.1.0 and 0.1.1 share one schema, so c3e never exercises either path.
8. --verify-only (O13.3e): on source or closure drift, keep running every row validator, add
   finding SOURCE_DRIFT (expected and observed digest), status DIAGNOSTIC_SOURCE_DRIFT, exit 2.
   HEAD stops at the first drift check and prints REHEARSAL_PASS/FINAL_PASS; neither is allowed.
   With this fix, every validator change can be tried on c3e raw in seconds before a remint.
9. P9: launch the consumer as its own child with a host receipt (it runs in-process today; the
   nested Godot receipt, pid 18804, is real).
10. P2 known limits: add security floor and key-loss recovery next to revoke/expiry/rotation.

## MINOR

11. P1: reject `zdoc` and `reviews` path segments in the archive denylist (none present now).
12. P3: host environment hash before and after the producer.
13. P5 Windows: Play after reinstall (Linux already plays).
14. P6: discovery from a second clean project directory with its own receipt.
15. Linux: inspect the container while running (State.Pid > 0) or rely on docker exit + logs;
    receipt field names uniform (`target_pid`, `exit_code`) across P7 and Linux.
16. P11 same-hash window resume is not needed now: Formal25 2-pair campaign ≈ 71 min, so ten
    pairs ≈ 5 h 53 min plus P1–P10 ≈ 27 min; a 19:30 start ends near 02:00. A mid-soak INFRA
    failure reruns with a new id on the same closure (O1.7).

## Suggested order (one pass, then one remint)

Fix 1–10 → run the fixed --verify-only on c3e raw: only rows lacking evidence in c3e may fail
(P7 receipts, P8 p8-host, P10 L01/L02 and trace, P11 10-pair) → commit → remint C3 (P11 one
cycle) → --verify-only → freeze → final through Scheduled Task started by 19:30 → --verify-only
in the morning → C6 two critics on one hash.
