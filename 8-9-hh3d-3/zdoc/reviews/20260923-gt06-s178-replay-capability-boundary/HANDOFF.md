# S178 resume handoff

## Current state

* GT01–GT05 remain accepted; GT06 is `IN_PROGRESS` with zero accepted full
  runs. GT07–GT10 remain unopened.
* S177 consumer pilot evidence is frozen and independently verified. It remains
  `AUTHORITY=0`, `pilot_acceptance=false`, and `gt06_acceptance=false`.
* S178 read-only replay inspection and the GT07–GT10 preparation tests are
  committed. No Godot, Blender, debugger, or benchmark process belongs to the
  current lane.

## Resume only when one of these facts changes

1. A supported replay contract is added for a consumer project or caller-owned
   input trace, with a new source closure and verifier; or
2. The owner approves an ADR that changes the evidence contract or acceptance
   route; or
3. A new, independently justified GT06 hypothesis is documented and passes
   the cheap capability preflight.

On resume, create fresh run/command IDs, freeze the affected source closure,
and run only the smallest test that distinguishes the changed condition. Do not
reuse S162–S177 identifiers or reinterpret the S177 pilot as GT06 evidence.

## Do not do while waiting

Do not rerun the unchanged formal campaign, add a live adapter by subclassing
`PreparedPlay`, loosen thresholds, or open GT07–GT10. Keep the packet,
failure history, and authority-0 labels intact.
