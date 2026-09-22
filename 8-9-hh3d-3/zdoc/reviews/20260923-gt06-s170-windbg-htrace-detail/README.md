# S170 htrace detail fixture (AUTHORITY=0)

`gt06-s170-windbg-htrace-detail-01` is a fresh bounded continuation enabled
by S169's successful CDB attach. It queried `!htrace` for all traces and the
two expected handle values while stopped at OPEN_BREAK, then recorded the
close diff and queried the same handles again before disable/detach. Target
and CDB both exited naturally with code 0 and no leftover debugger/fixture
process remained.

The raw detail output proves the target PID/TID, OPEN/CLOSE history, and that
no outstanding handles remained after close. It does **not** contain a
resolved caller module/offset for `CreateEventW` or
`CreateIoCompletionPort`; `!handle` ran after those handles were already gone
and returned Win32 error 6. The fixture is managed C#/.NET and was not a
Godot run. Keep attribution `UNKNOWN` and `AUTHORITY=0`; do not promote this
to GT06, F13/F14, leak, root-cause, or repair evidence.

The hard-coded detail values (`0x30c`, `0x310`) are an explicit diagnostic
limitation: the target JSON records the actual handles and the receipt does
not claim these queries were a complete dynamic binding. A future native
unmanaged fixture with local symbols would be a separate hypothesis, only if
its toolchain is available; do not retry this managed run or launch formal
GT06 from this packet.
