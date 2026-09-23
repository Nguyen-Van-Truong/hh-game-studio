# S184 bounded read-buffer candidate

AUTHORITY=0. No formal acceptance, no leak verdict, and no S181 root-cause claim.

S183 isolated the same 22.5MB journal without an engine and completed 1,000 HTTP
commands. Slow snapshots were predominantly waiting rather than thread CPU;
the exact scheduler/disk cause remains unknown. S184 therefore compares a
narrow performance candidate without changing integrity or timeout policy.

Four fresh Python processes ran stock-before, 256KiB scratch, 1MiB scratch and
stock-after, using the S182 copied-history/pending-HTTP fixture. All four actual
exits were zero, all host threads stopped, all private indexes closed, and all
original/copy history hashes stayed equal. There were 72 full-history checks
in total. Synthetic pending responses are fixture controls, not real admission
proof. Exact result files and process exits are recorded in `comparison.json`.

At the original 1ms polling cadence, the medians were respectively 65.440,
87.708, 47.601 and 60.997ms. The 256KiB candidate was rejected. The selected 1MiB
candidate reduced observed contention cost by about 22–27% against the two
stock observations. This small comparison cannot predict full-campaign latency
or RSS and does not prove the source of S181's intermittent timeout.

The runtime change only replaces repeated 64KiB allocated reads with one local
1MiB `readinto` scratch buffer. The buffer is released before `_snapshot`
returns; it is not retained or allocated before baseline sampling. Every byte
is still hashed; individual updates stay <=2047 bytes. The original size cap,
identity checks, accepted full replay on change, OS/process locks, fsync,
receipts, five-second terminal budget and all benchmark gates remain intact.
Short reads continue until EOF; overflow reads at most one byte beyond the cap.

Validation: six candidate stream tests, then 41 focused verified-journal,
private-index and HTTP producer tests, followed by 56 execution-binding,
installed-generation and backend tests. These are source regression results,
not native memory acceptance. The old 1MiB S143 diagnostic failure remains
preserved; this uses one reusable temporary buffer and does not erase that
unresolved observation or adjust any counter limit.

`binding-refresh/` preserves old/new metadata and proves the only change among
215 dependencies is `host/replay/verified_journal.py`; 217 execution files were
verified in a fresh interpreter. GT05 admission/assets remain unchanged. Two
individual atomic replacements fail closed between generations; this is not a
cross-file atomic or hot-upgrade claim. The helper is one-use and must not be
rerun. The pretty-JSON map hash and canonical closure hash are separate domains.

Comparison provenance: the executed comparison used the original S181 source
closure and an in-process candidate overlay. `compare_buffers.py` is retained
as executed and expects that old source's loop. Do not run it against the new
runtime and call that the same comparison. The S181 local archive and source
map preserve the old input; `read_buffer.py` is the comparison candidate, not
the runtime authority. Only `studio/host/replay/verified_journal.py` is the
installed implementation.

API references: [Python 3.11 binary I/O](https://docs.python.org/3.11/library/io.html)
and [hashlib GIL boundary](https://docs.python.org/3.11/library/hashlib.html).
The docs describe API behavior; the measured speed figures come only from the
retained local comparison. Formal validation must use a fresh campaign ID,
unchanged gates and new frozen source/binding hashes; no old partial samples
can be reused as successful runs.
