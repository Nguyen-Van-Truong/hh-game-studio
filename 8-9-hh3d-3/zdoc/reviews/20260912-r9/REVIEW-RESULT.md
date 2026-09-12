# GT-01 review checkpoint r9

`PLAN_REVISION=S21`, `CURRENT_VALID_WP=GT-01`, `IMPLEMENTATION=GT01_IN_PROGRESS`.
This package records a new candidate run after the S21 hardening changes. It
does not mark GT-01 accepted.

## Verified in this checkpoint

- Static plan and mutation gate: `PASS_STATIC_ONLY`, 41/41 tests.
- Bootstrap unit suite: 39/39 tests, including archive provenance, duplicate
  checksum rows, hardlink/path rejection, lock CAS/PID reuse, publication
  failure preservation, runner admission and strict trace parsing.
- Runtime `run_id=20260912T135056Z`: nine serial lanes passed. Godot headless
  and headed menu paths, menu Quit, Blender save/reopen and existing-file
  refusal were observed with host exits 0/2 and no owned-process leftovers.
- Pinned binary observation: Godot `4.7.2.stable.official.ed1daf0bf` and
  Blender `5.2.1 LTS` both match the lock hashes; archive verification is
  bytes-only and offline.

## Remaining acceptance gaps

The runtime is still a partial candidate. A complete source freeze and
redacted, independently reproducible package must be reviewed on the exact
current source hash. GT-01 still needs the TQ01 portability/reproduction
closure, the scoped TX12/TX14 checks, explicit rollback evidence over distinct
package identities, and two independent read-only critics recording the same
frozen source hash. Future GT-08 ABI/template/build and GT-10 full installer,
upgrade and uninstall acceptance remain out of scope here.

Raw process logs are kept only in this package after replacing workspace and
temporary-root prefixes with `$WORKSPACE` and `$RUN_ROOT`; no username or
absolute host path is part of committed evidence.
