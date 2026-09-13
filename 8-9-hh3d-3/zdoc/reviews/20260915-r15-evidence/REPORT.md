# GT-01 evidence binder (r16)

The binder validates a runner package while preserving the runner's
`CANDIDATE` status. It rejects `DIAGNOSTIC`, unknown, and `ACCEPTED` claims;
`READY_FOR_CRITIC` is eligibility only and never promotes a candidate.

Manifest paths use the exact `8-9-hh3d-3/studio/` prefix. Runner bindings use
exact studio-relative keys and are mapped to that prefix without stripping
arbitrary leading components. The complete on-disk studio closure is hashed
and compared for exact file-set equality, and a supplied closure hash must
match the recomputed value.

Every lane requires independently hashed stdout, stderr, and host JSON. Host
PID, start time, and exit are parsed and compared with the run record;
warnings, errors, invalid UTF-8, and non-empty stderr fail closed. Lane names
are exact (`import`, `parse`, `trace-headless`, `editor-headed`,
`trace-headed`), and all lanes must use the same pinned executable. The default
lanes are import, parse, and trace-headless. Editor-headed and trace-headed are
accepted only as a pair, with parsed editor postconditions, parsed headed trace,
and an independently hashed 640x360 PNG capture (`artifact_hashes`). Trace
lines are parsed from stdout and checked for ordered transitions, movement,
pause freeze, resume advancement, and quit; canonical headless `trace_lines`
must match its stream, while optional `headed_trace_lines` is checked when
present because headed capture metadata changes that JSON line.

Focused mutations are run with:

    python -m unittest discover -s 8-9-hh3d-3/zdoc/reviews/20260915-r15-evidence -p test_evidence_binder.py

The historical R16 package is intentionally not bindable after source edits:
it has no top-level `log_hashes` and its frozen closure is stale.
