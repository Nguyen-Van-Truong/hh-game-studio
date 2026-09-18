# GT06 S78 derived journal index candidate

AUTHORITY=0. Candidate WIP; GT06 is not accepted. Runtime checkpoint is 04b2f4dc. The S77 object diagnostic is supplemental and remains in its own package.

This package contains a fresh 49-file runtime closure manifest for source code as loaded by `run_benchmark_campaign.source_files()`, plus the affected replay/service source snapshot and an owned focused test capture. The first capture `s78-focused-02` intentionally failed because its working directory was the review package and Python could not import `studio`; it is retained as a launcher/evidence lesson. The corrected `s78-focused-03` ran from the repository snapshot root, exited 0, wrapper 0, timeout false, tree verified, and reported 72 tests with zero failures/errors/skips.

The focused lane covers the five journal protocol suites, replay benchmark command tests, ReplayService tests, and five new DiskJournalIndex tests. The prior complete replay suite on the same source edits was 391/391; a fresh full GT06 campaign has not run. No test result here is an acceptance verdict or a substitute for the required 10 fresh pairs × 35 batches campaign.

The candidate adds a disposable per-instance SQLite derived index for command/offset state and explicit close after service/producer drain. JSONL checksum, fsync, lock, compaction, tombstones and replay remain authoritative. Derived index failure after a durable append is `JOURNAL_INDEX_UNAVAILABLE` with outcome unknown; a later locked operation rebuilds from JSONL. The package does not claim an RSS bound, safe-write expansion, arbitrary gameplay authoring, or a full game.
