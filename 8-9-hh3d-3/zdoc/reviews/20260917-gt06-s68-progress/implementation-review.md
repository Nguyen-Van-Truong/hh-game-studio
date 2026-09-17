# GT06 S68 implementation review

2026-09-17 15:41 UTC. **Implementation review and bounded fix only; not acceptance or a TICK verdict.** No engines, GUI, benchmark workload, full test suite, production source edits, or commits were performed by this reviewer.

## VerifiedJournal: no concrete findings

Read `studio/host/replay/verified_journal.py` and its targeted tests against accepted `studio/host/core/journal.py`, including locking, loading, receipts, append, lease guards and compaction. No correctness/security regression was found within the accepted journal's existing trusted private namespace and cooperating-writer assumptions.

- The inherited permanent guard lock covers reload, the cached index and the operation; namespace alias checks remain in that path.
- A cache hit requires complete-file SHA256, byte count, file identity and policy equality. The matching file is still fsynced before a receipt or lease decision is exposed. Receipt bodies remain on disk and are decoded when accessed.
- A changed file, replacement, policy change or compaction invokes the accepted full reload, including index clearing, history validation and recovery fsync.
- Local append invalidates the cached digest before accepted validation/write/fsync/index updates. A failure cannot leave the old digest trusted. Only successful append extends a copy of the previous digest using the accepted serialized record and confirms metadata; an optional metadata failure leaves the cache invalid.
- This does not add protection against adversarial concurrent writes by the same OS principal outside the shared guard. Accepted core explicitly excludes that threat without isolation. Complete hashing is still O(file bytes) per operation; the optimization removes repeated full history parsing/canonicalization, not all history-dependent work.

The journal tests were inspected, not rerun during the active residency workload. Reviewed and unchanged SHA256:

| File | SHA256 |
|---|---|
| `studio/host/replay/verified_journal.py` | `fbd65fb03b7b6cf00211924e0977891f9a6df548f787fa62171e92fd34a860ab` |
| `studio/tests/replay/test_verified_journal.py` | `16abfa22a9baadd4957efd924c26c86c5d4c67cffda79a887c0e89a0cb893e30` |

## Reviewer probe P2 fixed

The preceding S67 review reproduced an owner leak when evidence directory creation or source staging failed after `PreparedReviewer.prepare()` but before the probe's `try/finally`. The only implementation change here is `studio/tests/reviewer/run_reviewer_probe.py`: protection now begins immediately after acquisition and includes all evidence staging. If both the probe body and cleanup fail, the original exception remains primary with the cleanup error chained as its cause. The real `PreparedReviewer.close()` retains the exact uncertain owner in `HELD_REVIEWERS`; a successful later close removes it.

Added `studio/tests/reviewer/test_probe_cleanup.py`. All **5 tests passed**, exit 0, using fake paths, patched evidence writes, and the actual prepared-owner cleanup lifecycle. They cover directory failure, first manifest write failure, partial source staging failure, interrupted staging, and concurrent staging/cleanup failure with exact-owner retention and successful retry. No evidence files, network, GUI or engine are created by these tests.

Repro from `8-9-hh3d-3/`:

```text
python -B -m unittest studio.tests.reviewer.test_probe_cleanup -v
```

| Changed file | SHA256 |
|---|---|
| `studio/tests/reviewer/run_reviewer_probe.py` | `d4bbb761406bce223178e83f96164f65f459aa138f958212267bf68eb69002ba` |
| `studio/tests/reviewer/test_probe_cleanup.py` | `654899bb92176b4d7d60aa05ac45853e55501741d74f3dc45c085018705246b2` |

This resolves the remaining staging-cleanup finding in `../20260917-gt06-s67-reviewer-implementation-review.md`. The changed diagnostic driver has not been rerun against a native GUI by this reviewer; earlier native evidence retains its original source binding.
