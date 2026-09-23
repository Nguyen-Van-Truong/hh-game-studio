# S180 — Windows tracing capability boundary

`RUN_ID=gt06-s180-wpr-capability-01`  
`COMMAND_ID=cmd.gt06.s180.wpr-capability.1`  
`AUTHORITY=0`  
`ENGINE_STARTED=false`

This is a read-only capability preflight. It checks whether the installed
Windows Performance Recorder/ Application Verifier tools can provide a
supported creator/owner and API-return-stack boundary for the GT06 handle
question. It does not start Godot, Blender, a benchmark, or a trace session.

`wpr.exe` is present and advertises the built-in `Handle`, `Heap`, and
`HeapSnapshot` profiles. A status query reports that no recording is active.
The profile list does not prove per-handle creator stacks or bind a handle to
the Godot child lifetime. `appverif.exe` is present, but even its help probe
requires elevation in this session, so it is not a usable bounded integration
without an external privilege change.

Decision: keep GT06's frozen source, profile, timeout, baseline, RSS and
10x35 verifier unchanged. This capability boundary does not justify S181, a
formal retry, a gate change, a leak/root-cause claim, or an acceptance claim.
It is retained as `AUTHORITY=0` evidence. Resume only if an elevated,
supported integration can bind creator/owner and return stacks to the actual
child lifetime, an owner ADR changes the evidence contract, or a genuinely
new route passes its own cheap preflight.
