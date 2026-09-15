# S36 retained private event log — CANDIDATE

Closure `c4db7728b0b606d6574d24a78fde5eaaec99bed7934d280d0e56cec0d8e280f1`:
76 source files, 9 candidate artifacts, protocol **224/228 passed + 4 explicit
skips**, bootstrap **56/56**. Actual host exit/tree checks passed and the full
source/snapshot remained unchanged. Golden results still contain 2,396 rows
and nine Godot negatives. This is solo verification, not gate acceptance.

New internal code: `private_events.py`, its contract and 18 real Windows tests.
It adds a protected, retained-handle, framed/hash-chained event stream with an
expected-head append, durable read barrier, high-water witness and retained
cleanup ownership. Existing protocol/transport/native endpoint files are
byte-identical to S35. S35 native counter evidence remains valid for that
unchanged subset; **the S35 native client does not exercise this new stream**.

Focused diagnostics are preserved and bound by `diagnostic-manifest.json`
(19 files). Run01: 14 tests, one fixture error, actual exit1. A live os.link
attempt returned Windows sharing violation32, contrary to the test's assumption
that it would always succeed. The corrected test allows the observed native
denial or verifies admission refusal after a successful alias; it additionally
creates a real alias after close and requires reopen rejection with unchanged
bytes. This does not generalize sharing modes into a sandbox guarantee.

Run02: 16/16 passed. The subsequent audit added an explicit final EOF check
after frame readback and tests for an unexpected tail at that boundary and a
reader concurrent with an append/flush. Run03: 18/18 passed, followed by the
complete candidate run. Exact source for runs01/02 was reconstructed and
matched against the pre-run SHA256 records before archival; run03 source
matches the candidate. No prior log was overwritten or recounted as a pass.

Four child processes exit deliberately at pre-write, partial-write, post-write
and post-flush cuts. Tests capture exit73 plus an armed marker, then reopen
from trusted identities/witness in fresh processes. Complete records become
observations after a fresh flush; partial history remains quarantined and byte
preserved. This is not a successful command or physical power-cut proof.

Whole valid suffix truncation is detected only when the trusted witness covers
it. A test deliberately demonstrates the limitation of an older witness.
No complete selector, intent/reservation owner, consumer adoption, recovery
repair, release namespace publication or worker-to-staging integration is
claimed. General safe_write/atomic_replace remain false. GT-03/04 remain gated.

```powershell
python 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s36-audit/verify_evidence.py
python 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s36-audit/verify_git_bytes.py index
python 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s36-audit/verify_git_bytes.py HEAD
```

The latter reconstruct exact source/candidate/native-subset/diagnostic artifacts
from Git blobs into a disposable directory; this verifies stored evidence, not
a rerun of the engine or native client. Each output names the actual checked
commit. Source/evidence hashes are unaffected by checkpoint metadata.
