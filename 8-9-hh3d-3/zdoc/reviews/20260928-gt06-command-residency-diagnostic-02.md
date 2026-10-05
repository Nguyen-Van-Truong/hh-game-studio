# GT-06 command-residency diagnostic 02 — interrupted prefix — 2026-09-28

`AUTHORITY=0`; this is a command-only scaling diagnosis, not a formal
campaign and not acceptance evidence.

Run `gt06-status-gap-diagnostic-02` reached 18 complete 1,000-command batches
(batch indices 0–17). Its retained summaries show a maximum command-lane gap of
931.8363 ms and no batch over the unchanged 2,000 ms O1 boundary. Journal size
grew from 984,817 to 17,811,595 bytes while the resident process stayed bound
to one host identity.

The Codex execution handle was interrupted before the scheduler wrapper wrote a
terminal result, child exit, or cleanup record. The Windows processes are now
gone, so this prefix has no authoritative actual exit and must not be called a
PASS or a product failure. Raw batches and summaries remain under
`studio/.local/reviews/gt06-status-gap-diagnostic-02/`; no formal campaign was
started and no Godot or Blender process ran.

Run03 is the fresh demand-only scheduler run using the repaired failure
evidence path. It is the only active residency diagnostic; do not resume or
rebind run02.
