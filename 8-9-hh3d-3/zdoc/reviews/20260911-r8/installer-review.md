# GT-01 offline archive/bootstrap review (read-only)

Scope reviewed: `studio/build/bootstrap/verify_archive.py`,
`install_toolchain.py`, `studio/tests/bootstrap/test_archive_and_install.py`,
`studio/toolchain.lock.json`, and the GT-01/GT-02 requirements in the studio
plan.  The test file passes locally (3/3).  This is a security/correctness
review only; it is not a GT-01 acceptance or critic signature.

## Findings

### P1 — Crash lock is a permanent write denial (stale-lock recovery is absent)

`lease()` deliberately leaves `.mutation.lock` after an interrupted process and
always opens it with `xb`.  Any subsequent operation then fails until recovery.
The helper now records PID/time/nonce and exposes an explicit `recover-lock`
command that requires a dead owner and a minimum age; it never silently reclaims
a recent/live lock.  This is cooperative local recovery, not hostile-process
fencing, and remains a documented limitation.
This is a concrete reproducible case: create `root/.mutation.lock`, then call
`install(..., root)`; it rejects before making progress.  GT-01's safety text
requires crash/rollback behavior and GT-02 requires lease/fencing semantics;
candidate use needs an explicitly authenticated stale-owner recovery protocol,
or the helper must remain diagnostic-only.

### P1 — Manifest closure records are vulnerable to a file replacement race

`closure()` now records digest and size from one identity window and rechecks the
file identity after reading.  This reduces ordinary replacement mistakes but is
still not a handle-relative hostile-path primitive.

### P2 — Extraction and commit durability are limited

The staged files and manifest are fsynced, and rename is same-volume, but the
containing directories are not fsynced.  After an OS/power failure, a successful
rename may be lost or leave an incomplete directory entry despite the returned
receipt.  `publish()` similarly fsyncs the temporary state file but not the root
directory.  This is a durability gap rather than an archive-integrity bypass;
the caller must treat post-crash state as requiring `read_package`/CAS
reconciliation.

### P2 — Verifier's path identity checks are not race-proof safe-open

`verify_archive()` explicitly documents this: it lstat-checks paths, then opens
them later.  A concurrent replacement can pass the initial checks and be opened
as another regular file before the final identity check (the check detects many
cases, but does not bind the opened handle).  The installer inherits this for
lock/archive/sums and should not be exposed as a hostile-path sandbox; use
handle-relative opens where that threat model is required.

## Positive controls observed

The lock schema/status, official URL construction, SHA-256/SHA-512/size checks,
detached-sums uniqueness, bounded reads/archive expansion, duplicate/case-folded
ZIP names, basename/device/traversal checks, regular-file and hard-link checks,
immutable content-addressed package directories, and explicit state CAS tokens
are coherent and fail closed in the reviewed paths.  Activation and rollback
read back package manifests before publishing state, and no PATH mutation or
process launch occurs.

## Disposition

**Candidate retention: conditional.**  The helpers are suitable to retain as an
offline, cooperative, diagnostic candidate after documenting the explicit stale-
lock recovery and the non-hostile/race limitations.  They are not safe
to call an accepted GT-01 installer or a hostile-code sandbox until P1 lease
recovery/fencing and closure consistency are fixed and independently reviewed.
