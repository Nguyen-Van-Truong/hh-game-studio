# S254/S255 API-return diagnostic

`AUTHORITY=0`; `formal_acceptance=false`; this packet does not change GT06.

S254 on an owned Python fixture proved a genuinely distinct boundary: CDB stopped at `NtCreateEvent` and `NtCreateIoCompletion`, captured a native stack and function return, and the returned handles matched the fixture ground truth. S255 applied the same route to Godot started suspended and captured the loader/API stack and return values on the target PID. The Godot attempts then hit a debugger/termination lifecycle boundary: the editor did not produce a natural exit within the bounded run and cleanup ended with target exit 2; Job active count reached zero and the Job handle closed. This is not an editor leak, ownership, or root-cause finding.

The raw captures remain under `studio/.local/reviews/gt06-s254-api-return-01`, `gt06-s255-godot-api-return-05`, and `gt06-s255-godot-api-return-12`. Do not use this packet as a formal run, as F13/F14 evidence, or as permission to change the 10x35 gate.
