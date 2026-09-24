# S235 — S232 formal terminal review

`gt06-s232-formal-01` is a retained failed prefix, not a formal acceptance.
The campaign completed batches 0–8, with batch 8 failing at `joint_observation`
when the editor held-handle counter was 554 against the batch-4 baseline 552.
The host handle count stayed 204; editor objects/resources stayed 71130/6 and
RSS decreased. This is a gate-row observation only and proves no leak, owner, or
root cause.

The S232 source also inserted an unconditional post-ACK settle probe. That
changes cadence by at least 1.1 seconds per batch and is absent from the formal
assembly. The failed screen is raised before the probe can emit `counter-probe-08`;
raw contains only probes 00–07. The probe campaign is therefore diagnostic and
cannot authorize a formal retry or replace the frozen gate.

Cleanup evidence is retained in the immutable archive. The host wrapper exited
1; the import target exited 0. The child cleanup observed the editor target exit
code 2 through the retained identity handle after forced cleanup; this is not a
natural-exit proof. Jobs reached zero/closed, wrapper/probe handles were released,
and producer threads/sockets/journal were closed. The supervisor return receipt
is exit 1 with actual supervisor exit still unknown; scheduler state is not exit
proof. All raw files and attempts remain Authority 0.

A future diagnostic may sample the same retained editor handle immediately after
ACK and during a bounded idle period after the first gate failure, without issuing
another start permit. It must preserve the original failure and cannot alter the
formal timeout, baseline, counter, RSS, profile, or acceptance gate.

Verify the sealed raw package with:

`python -B zdoc/reviews/20260924-gt06-s235-terminal-review/verify.py`

from `8-9-hh3d-3`. This packet is a read-only terminal review, not GT06 evidence
for acceptance.
