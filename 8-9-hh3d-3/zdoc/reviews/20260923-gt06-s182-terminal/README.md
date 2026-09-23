# S181 terminal preservation and S182/S183 boundary checks

AUTHORITY=0. GT06 remains IN_PROGRESS with zero accepted full runs. These
diagnostics and partial batches are excluded from F13/F14 and acceptance.

S181 ended with `TERMINAL_TIMEOUT` in batch 22 after 22 completed batches.
The last of 869 partial command rows was `b22.admitted.172`: admission returned
QUEUED, all 47 lookups returned pending without a transport failure, and the
same digest later had a durable COMMITTED/readback record. A late durable result
does not satisfy the client's unchanged five-second terminal budget. The one
earlier recovered lookup transport failure belongs to a different window.
`failure-analysis.json` binds the raw hashes and preserves the exact timing.

Raw preservation: `raw-manifest.json` indexes 379 verified archive members.
The ZIP remains under `studio/.local/archives`; selected small cleanup and exit
receipts are exact copies here. Host actual exit 1 and import actual exit 0 are
retained. Editor target and supervisor natural exits remain UNKNOWN; helper and
scheduler results do not fill those gaps. Jobs/probes/threads report clean
teardown. The demand-only S181 task was retired after preservation.

S182's Python-only copied-history differential completed with actual exit 0,
closed journal and stopped host threads. Eighteen complete history checks show
some overhead from 1ms pending polling, but do not reproduce the second-scale
S181 delay. No cadence, timeout, source or gate change was made.

S183 restored the retained journal to an isolated command fixture and ran one
original 1,000-command HTTP batch with wall/thread-CPU, fsync, SQLite and GC
observations. It completed in 252.006472 seconds, actual exit 0, no dropped
commands, 500 inspect / 300 rejection / 200 admitted commands, 200 effects and
the separate no-effect Cancel. Maximum response gap was 846.6948ms; maximum
terminal latency was 1348.4496ms. Cleanup reports all threads stopped, probe
released and private index closed. Eleven raw files are in the separately
hashed S183 local archive, indexed by `s183-summary.json`.

Slow S183 snapshots used 507–580ms wall time and 47–109ms thread CPU. The
retained GC tail maximum was 0.598ms. The phase tail is bounded, not a full
distribution; `slow` holds only events at least 500ms. These observations do
not identify exact disk or scheduler ownership and do not prove S181's cause.
They justify comparing bounded reusable read buffers as a performance
candidate; all bytes, identity checks, locks and fsync must remain verified.

Lessons: check the attempt's child failure AND sibling supervisor, rather
than only the campaign root. Never infer an ACK deadline from admission-to-last
response latency: the terminal budget starts after admission. Preserve failed
collector attempts separately and repair metadata without replaying the engine.
The Python-to-Windows-PowerShell module-path issue is recorded separately in
`collector-lessons.json`; it was not an engine failure.

The old full plan is exact at `plan-before-s182.txt`, hash in the raw manifest.
402 historical lines were removed from the current plan's running status;
the requirement tail starting at the S76 capability clarification is unchanged.
No historical failure, source, gate or reviewer verdict was deleted.
