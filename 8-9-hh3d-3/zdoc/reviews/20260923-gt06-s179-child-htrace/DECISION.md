# S179 decision memo — GT06 attribution lane

`RUN_ID=gt06-s179-child-htrace-01`  
`COMMAND_ID=cmd.gt06.s179.child-htrace.1`  
`AUTHORITY=0`  
`DECISION=WAITING_EXTERNAL_INPUT`

## Decision

Do not launch S180 with the S169–S179 child/CDB/htrace hypothesis and do not
retry the formal GT06 campaign without a new supported boundary. The current
evidence does not justify changing a gate, baseline, timeout, RSS policy or
source/profile pin.

## Evidence reviewed

- S179 attached CDB to the verified Godot child PID `31048`, not the console
  wrapper PID `36336`; exact-line create/close markers and htrace output were
  captured.
- The wrapper exited `0`, but the child exit was not independently retained.
  CDB returned `2147942430` (`0x8007001e`). No Job-object or native
  `CloseHandle` closure receipt was captured.
- Htrace handles `0x464` and `0x3f8` are not bound to the fixture file or to
  the S153/S156 counter-growth rows. `ATTRIBUTION=UNKNOWN` and
  `AUTHORITY=0` remain the only valid interpretation.
- The cheap preflight still finds the same CDB version/hash and Godot binary;
  no matching PDB or supported attribution integration appeared. No owned
  Godot/CDB/WinDbg/Blender process remains.

## Acceptance boundary

GT06 remains the unchanged 10 fresh host/editor pairs × 35 batches gate with
full dataset, hashes, actual exits, trees, jobs, handles and two new critics.
Attribution is diagnostic-only unless an owner ADR explicitly changes that
policy. S179 is excluded from F13/F14, the GT06 dataset, leak/root-cause
claims and formal acceptance.

## Resume condition

Resume this lane only after one of these external changes is real and
recorded:

1. a supported integration that binds creator/owner and API return stacks to
   the actual child lifetime; or
2. an owner ADR that changes the diagnostic/acceptance policy; or
3. a genuinely distinct, bounded hypothesis with a cheap capability preflight
   proving finite output, exact process lifetime binding, and cleanup capture.

When resumed, allocate a fresh run and command ID, preserve all S153–S179 raw
evidence, run only the affected bounded diagnostic first, and keep the
formal GT06 verifier and all gates unchanged.

This memo is a read-only decision record. It does not open GT07–GT10 and does
not claim the consumer pilot is a complete game.
