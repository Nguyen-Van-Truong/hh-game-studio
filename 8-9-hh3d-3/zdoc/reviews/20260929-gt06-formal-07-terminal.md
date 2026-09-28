# GT-06 formal07 terminal closeout — 2026-09-29

## Verdict

Campaign `gt06-o4-formal-07` did not produce an accepted pair. The primary
classification is `PRODUCT_FAIL` with child error `TERMINAL_TIMEOUT` at batch
31. The run is not eligible for a critic package or GT-06 acceptance.

The raw watchdog also persisted `classification=INFRA_ABORT` with
`reason=FOREIGN_ENGINE` at sample index 934. This is a simultaneous teardown
signal, not a replacement verdict. The harness contract and its regression
test make an existing `child-failure.json` take precedence over a later
watchdog stop, so the parent record correctly remains `PRODUCT_FAIL`.

## Frozen identity

- Campaign: `gt06-o4-formal-07`
- Run: `gt06-o4-formal-07.r00.a01`
- Source closure: `d64c4ce399f5a79153d8daea289ca087b4f07aed0622ac02788f0cbe666ca475`
- Profile: `9dfa0ae003577e8607e28e722089328933d60e6cdb5b1ae1c5e978b3ad9d335e`
- Campaign hash: `b81f43fb71d4fa74666a6b928da9fd26745be16af0cd47ce284a0e3beda26d28`
- Completed batches: 31 of 35; pair 2 was not started
- Formal acceptance: `false`; accepted pairs remain zero

## Terminal evidence

`child-failure.json` records `TERMINAL_TIMEOUT`, `completed_batches=31`, and
`formal_acceptance=false`. `child-terminal-cleanup.json` records the failure at
batch 31/commands. Host and editor target natural exits were not recorded and
must not be inferred. The import observer recorded exit 0. Host/editor wrapper
cleanup closed their Jobs with `active_count=0`, `zero_observed=true`, and no
retained wrapper handles. The supervisor returned code 1; its record also says
that a natural supervisor process exit was not yet observable. These facts are
kept as observed, without upgrading the run to PASS.

At watchdog sample 934 the foreign list contained
`godot_v4.7.2-stable_win64.exe` PID 18784. The same PID appeared in the
campaign-owned inventory in earlier samples and disappeared from that inventory
when cleanup was underway, while the process was still visible. This explains
why the watchdog persisted the unverified foreign-engine signal, but it does not
erase the preceding child timeout. The teardown race must be reviewed before a
new formal source is frozen; no gate, timeout, or verdict rule is relaxed.

## Raw closeout

Raw campaign and supervisor evidence were copied into the separate ignored
closeout directory:

`studio/.local/reviews/gt06-formal07-closeout-20260929/`

- Files: 458; bytes: 153128377
- Raw manifest SHA-256: `3cc2067d96a484e69c94b9c02495cf79d0ff5022dd532fcea8da632f441cd145`
- Raw ZIP SHA-256: `fc670c225ac74aeeaa9ad26d338e74cec959c3491fafc5425c4bb85934209aef`

The original campaign raw directory is unchanged. No run is resumed and no
new campaign is dispatched from this closeout.

## Next gate-preserving action

1. Review the watchdog/owned-process teardown ordering and add a regression
   test for the observed PID-18784 race, without changing O1/O4 thresholds,
   timeout, or child-failure precedence.
2. Only after that repair is verified, freeze a new source closure, run a fresh
   O4.1 preflight and one-minute CPU observation, then use a new campaign ID.
3. A future run must still complete both fresh 35-batch pairs and pass all
   actual-exit, Job/tree/handle, dataset, and source-hash checks before the
   owner receives a CRITIC_PACKAGE.

