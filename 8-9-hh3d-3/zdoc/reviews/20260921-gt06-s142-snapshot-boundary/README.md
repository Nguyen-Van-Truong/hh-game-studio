# S142/S143 snapshot scheduling candidate

AUTHORITY=0. No GT06 acceptance, no F13/F14 samples. Original gates, native
benchmark, profile, timeouts, memory policy and workstation settings unchanged.

S141 failed at batch4 inspect.364 admission. The retained port/QPC/root join
places the delay in two full-history snapshots: 733.7135ms and 1674.4389ms.
The second crossed the client deadline; append took 49.6508ms after it.
Exact journal ID/digest later records QUEUED then CANCELED_BEFORE_APPLY.
Client UNKNOWN remains correct. The trace cannot separate read/hash/fsync.
See S141 terminal-01/failure-analysis.json and the 82-file retained packet.

The no-engine S142 probe used a byte-exact copy of the 4,634,619-byte history.
Twenty original snapshots completed, maximum13.3083ms. A controlled in-memory
hash comparison with an owned synthetic Python competitor gave stock64KiB
updates830.7–1105.6ms versus <=2047-byte updates11.1–44.6ms. Whole-snapshot
profiling showed repeated file reads also waiting: stock2326–2627ms; small
hash updates alone1213–1284ms. Keeping all original verification/fsync but
using1MiB reads and <=2047-byte digest updates gave186–260ms versus stock
725–2924ms with contention. Uncontended stock9.3–10.3ms, candidate12.0–12.3ms.
All digests/identities/history matched and owned competitors stopped.

This proves an avoidable scheduling mechanism under controlled contention,
not that it was the sole cause of S141. CPython documents release of the GIL
for hashlib updates larger than2047bytes:
https://docs.python.org/3.11/library/hashlib.html

The narrow runtime candidate changes only VerifiedJournal._snapshot read and
hash chunking. It still reads/hashes every byte, validates size/file identity,
honors max_bytes, falls back to accepted parsing for changed history, and
requires the same recovery fsync. It releases each memoryview/read chunk
before the next read; temporary allocation and coupled RSS still need checks.
No switch interval, priority, timeout, baseline or acceptance change.

Coordinator observed45 unittest cases pass in12.643s: verified_journal,
disk_journal_index, journal_index, journal_durability, journal_cas,
transport_pending_lookup. A new test covers exact digest, late-buffer byte
mutation and tail, while existing tests keep corruption/fsync/replay failures.
Candidate53 closure4bd7972b803a877777166ece82d85b6f841755d82bcec42ed78c28ae78c78a01.

S143-01 wrapper failed before engine because runpy's returned globals dict
was not the function globals. The existing S102 output prevented any write;
keep this failure. S143-02 is a fresh direct copy of the old driver with only
RUN_ID changed. Its import plus20HTTP commands completed14.390s, actual
host33612/helper50076 exits0, Jobszero/closed, source/cleanup checks passed.
This is functional preflight, not the original1000HTTP+100native workload.

Next: one bounded7batch coupled candidate, original gates and stock native;
check transient memory and admission behavior before another formal campaign.
Installed217 still represents S135/S138: its binding must be refreshed with
an exact dependency delta before claiming current service/repair acceptance.
Do not rerun unchanged art or reuse historical signatures as current proof.
