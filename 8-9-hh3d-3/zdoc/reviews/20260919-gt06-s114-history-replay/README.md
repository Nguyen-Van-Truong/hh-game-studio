# S114 — exact-history HTTP attribution

AUTHORITY=0. Supplemental only; no F13/F14 samples, engine run, leak verdict or acceptance.

S110 failed at admission after a roughly 2.2 s verified snapshot. The S111 base
Journal timings do not explain that service path; S112's exact VerifiedJournal
was fast on an unchanged isolated copy. S114 tests the missing combination:
the original HTTP producer, concurrent fixture host and exact preserved history.

`history_replay.py --check` validates the 53-file runtime closure, original
profile and S110 seed without starting a host. `--launch` refuses an existing
`run-01`, freezes sources/helper/history, then uses the existing BenchmarkProcess
owner for a single bounded child. It never launches Godot.

The child seeds 5,797,257 bytes / 8,292 records with SHA-256
`8bc2e17e06b11051cb2cba9f5110c6afb268bce87c6be990c0c20b80506ce4f7`.
It runs one original 1,000-command 5/3/2 mix plus Cancel, with original 2 s
transport and 5 s terminal deadlines. A new project/revision0 and new IDs avoid
pretending to restore historical leases/effects. This is final S110 history,
not a reconstruction of the exact bytes/interleaving at its failed command.

Additional wrappers measure wall/thread CPU around unchanged snapshot, reload,
load, append and Python fsync calls. Nested spans overlap; their sums cannot be
added together. Non-CPU wall time cannot separate I/O, GIL, lock wait or OS
scheduling. SQLite's internal sync is not Python os.fsync. Wrapper overhead is
included, not subtracted. No thresholds, lock policy, journal semantics or
SQLite FULL/DELETE policy change. CPU timings only attribute the measured call.

The child has a 210 s cooperative budget and parent a 240 s work budget; owned
cleanup follows. Raw remains in ignored `run-01/`, including the original seed,
appended journal, copied runtime, phase recorder and actual process evidence.
Results must be read after terminal; launch is not completion.

## Earlier probe provenance correction

S113 `../20260919-gt06-s113-host-contention/result.json` is the retained result
of an empty-history, synthetic-observer probe, not the seeded experiment. It
reports 1,000 commands / 953,973 bytes and a 220.0106 ms gap. The temporary
script was dispatched twice with the same r01 ID and output path; only the last
result (PID 3432) remains. The first dispatch's terminal result was not retained.
An earlier directory-exists harness failure was also overwritten. None of
these missing records can be recovered by writing retrospective raw evidence.
The journal was temporary and the phase snapshot preceded cleanup. Keep the
remaining result for context, with these explicit gaps, excluded from acceptance.

Lessons applied: exclusive run directories; capture and retain exec session IDs;
own and record actual target/helper exits; freeze driver and seed before launch;
observe phases after cleanup; never rerun a lost-observation ID.
