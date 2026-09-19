# GT06 S104 closeout

This folder contains derived, read-only verification for S103 diagnostic
captures. It is not a formal GT06 campaign and cannot produce an acceptance
sample. The S103 raw roots remain under `studio/.local/reviews/` and are kept
immutable.

The `save-boundary/` package fixes and re-runs the reader predicate against the
same raw input hashes. It does not alter `benchmark_native.gd`, the profile,
the source closure, or any raw capture.

The `retained/verification.json` package was generated before the later
S104 documentation-only commit and therefore records its parent commit as
`349dc40a`. That field is historical provenance for the retention pass; it is
not a claim that the diagnostic ran against the later plan text. Source and
profile pins inside the package remain the authoritative run bindings.

Known gaps are intentionally preserved: diagnostic editor target exits are
missing for the bounded prefixes, earlier preflights lack complete owner exit
records, and no natural target exit or formal PASS is inferred. The retained
package is `AUTHORITY=0`, excluded from F13/F14 and the final GT06 dataset.
