# S30 coordinator verification

Frozen candidate: `../20260915-gt02-s30-01/`.
Closure: `60799065f406fbb3b13d2dc0df093477210927f86e84b54175dfd36351521a1a`.

The official snapshot run completed 154 protocol tests (150 passed, four explicit
platform skips), plus 56 bootstrap tests with no skips. The coordinator verifier
rehashes 62 source files and nine artifacts, validates host exits/process ownership
and child completion markers, and compares 2,396 Python/Node/Godot canonical rows
and nine Godot negative cases. `verification.json` binds P-01 through P-22 to exact
executed test IDs and preserves the limits of each proof class. This verification
is not an independent critic verdict.

## Changes and failure evidence

S29 critic A reproduced readable terminal bytes being treated as COMMITTED after
fsync failed. Reload now opens a writable journal handle and completes a successful
fsync barrier before exposing receipts. S30 preaudit B independently reproduced six
native guard/reload failures returning REJECTED for an already committed command.
The coordinator reproduced four of those failures as a failing test before fixing
phase classification; the final regression covers all six and four socket routes.
`JournalError.outcome_unknown` records local failure provenance, so guard/reload
failure returns UNKNOWN while a verified new-admission capacity refusal remains
REJECTED. Safe command IDs survive error responses; untrusted/secret IDs do not.

The coordinator promoted preaudit A's five-mode write/partial-write/flush/fsync and
fresh-interpreter/archive diagnostic into the frozen regression suite. A new final
critic A is therefore reviewing this candidate, rather than treating its test author
as an independent acceptance critic. Historical verdicts remain on their original
hashes. The dedicated UNSUPPORTED_OPEN_LANE denial and fixed guidance now match the
plan's literal contract, with real-wire no-effect/process-launch assertions.

The writable reload handle follows the documented Windows write-access requirement
for [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers).
Python documents flush followed by [os.fsync](https://docs.python.org/3/library/os.html#os.fsync)
for buffered files. These tests inject I/O failures; they are not real power-loss
or engine publish-recovery evidence.

## Remaining boundary and reproduction

Windows file mutation remains UNSUPPORTED and TX15's availability GAP stays open.
Read identity, safe rejection, trusted create-only publish probes and token access
checks do not prove a consumer sandbox or destination identity CAS. The Windows
probe report records an owned TEMP cleanup denied by automatic approval review;
that diagnostic does not claim a clean filesystem. Source official tests have their
own captured process-tree results, separate from this diagnostic cleanup limitation.

From the repository root:

```powershell
python 8-9-hh3d-3/zdoc/reviews/20260915-gt02-s30-audit/verify_evidence.py
python 8-9-hh3d-3/zdoc/reviews/20260915-gt02-s30-audit/verify_git_bytes.py index
```

The Git verifier reconstructs the frozen source/artifacts and preserved S29 plan
archive from exact blobs and reruns only the stored-evidence verifier in isolated
Python. `HEAD` selects the committed bytes after checkpoint. Source stays frozen
through independent review; coordinator acceptance remains separate and gated.

## Coordinator decision

Both reviewers verified the same closure. A recommends FAIL/TICK=no because
TX15 safe-write is unavailable; B recommends PASS/TICK=yes for the bounded
fixture baseline with its explicit unsupported capability. Neither reproduced
a remaining journal/transport defect. `coordinator-decision.json` binds both
reports and keeps GT-02 CANDIDATE. The plan clarifies that valid safe rejection
does not close the required capability GAP; no downstream mutation is opened.

Implementation/evidence checkpoint: `74d1cc2`. The post-commit HEAD check rebuilt
62 source files and nine artifacts from that commit, then verified the stored
evidence in isolated Python with exit 0. See `git-byte-verification-head.json`.
