# S166 static DbgEng contract audit

`RUN_ID=gt06-s166-static-audit-01`  
`COMMAND_ID=cmd.gt06.s166.static-contract.1`  
`PLAN_HASH=7203d567ce822974d21364b6cd083ed64d30247e809533a78b021bbe154eb899`  
`SOURCE_HASH=fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde`  
`AUDIT_SCRIPT_HASH=343cc7a6f6734238e6f05d4d95360c5c78273b242dbb06c6da0eb3cd873604ec`  
`PASS=STATIC_AUDIT_PASS_ONLY`  
`AUTHORITY=0`  
`PROCESS_EXIT=NOT_APPLICABLE_STATIC_AUDIT`  
`BLOCKER=runtime debugger attribution is still unproven`  
`NEXT_ACTION=obtain a supported debugger integration or owner-provided debugger environment, then make one bounded runtime attempt`

The verifier reads the installed SDK header and the retained S162, S163, S164
and S165 source bytes. It does not start an engine, load `dbgeng.dll`, attach
to a process, or write a generated evidence packet. The header hash is
`3daa5d6aebbfca3aefcee6fd0b5b34abd2eebf2a0313facb3f5939da6ae8defa`.

The parsed slot counts are `IDebugClient=48`, `IDebugControl=95` and
`IDebugSystemObjects=32`; all begin with `QueryInterface, AddRef, Release`.
There are 52 literal vtable calls. Forty-six are consistent with the SDK
header, all calls in S162 and S163 are consistent, and six calls are the
expected historical S164/S165 experiment: slot 90 resolves to
`SetExceptionFilterParameters` rather than `WaitForEvent`, and slot 63
resolves to `Evaluate` rather than `Execute`. No unexpected static mismatch
was found.

This closes the index-count question and makes S164/S165 **ineligible** as
independent runtime attribution attempts. It does not turn S162/S163 into a
PASS: neither placed a breakpoint or proved handle ownership, and all four
packets remain `AUTHORITY=0`, outside F13/F14 and the GT06 dataset. The
`0x8000FFFF` result is retained as a runtime boundary only; this audit does
not infer that it proves an environmental root cause.

The regression suite has eight tests. It checks variadic SDK macros, comments
and strings, exact literal calls, dynamic-slot rejection, unknown objects,
out-of-range slots, unsupported macros and IUnknown/duplicate invariants.
It passed with exit 0. The static result is not a GT06 acceptance result:
GT06 still needs 10 fresh host/editor pairs × 35 batches, complete dataset
and process/cleanup evidence, and two new same-hash critics with `PASS/TICK=yes`.

The owner handoff and its bounded preconditions are recorded in
`DEBUGGER_HANDOFF.md`; it is planning-only and does not install or run a
debugger.
