# GT-06 functional seal preparation — S81

`AUTHORITY=0`; `STATUS=NOT_FINAL`. This directory is a preparation map, not a
critic report and not an acceptance package. It cannot promote GT-06 while the
S81 benchmark has a partial failure.

The map binds unchanged dependencies to their original source closures and
keeps the S81 affected lanes separate:

- S79 backend/service and GUI evidence remains under its original run IDs.
- S69 managed replay/runtime evidence remains under its original run IDs.
- GT-05 accepted pipeline evidence remains under its accepted closure.
- S81 admission/cleanup/HTTP supplements are diagnostic and affected-lane
  evidence only; they do not turn a partial campaign into a full run.

The final version may be generated only after a complete 10 fresh process-pair
campaign (35 batches per pair), exact source/profile/workstation bindings,
actual target/helper exits, owned-tree and handle proof, all failed-attempt and
supervisor-launch inventory, and the campaign's strict dataset summary. Two
independent read-only critics must then review that one frozen closure and
write `PASS` plus `TICK=yes`.
