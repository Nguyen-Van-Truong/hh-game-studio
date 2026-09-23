# S179 corrected child-process attribution diagnostic

`RUN_ID=gt06-s179-child-htrace-01`

`COMMAND_ID=cmd.gt06.s179.child-htrace.1`

`AUTHORITY=0`

This is one bounded diagnostic fixture, not a GT06 campaign or acceptance
sample. It preserves the stock source/profile and only tests whether the
Windows console wrapper's child process can be observed by the existing CDB
handle tracer. S171 attached to the wrapper PID recorded by `Popen`; the
console wrapper then creates `Godot_v4.7.2-stable_win64.exe`, so S179 records
both identities and attaches only to the verified child image.

The diagnostic is excluded from F13/F14, the GT06 dataset, leak/no-leak and
root-cause claims, repair authorization, and formal acceptance. A failure or
missing child is retained evidence, not a reason to retry the formal campaign.

The helper attempted a 60-second loop bound, but did not bound every child
lookup/helper wait. The observed run ended in about 23 seconds. This is a
limitation of the diagnostic harness, not a verified hard deadline.

## Result

The fixture reached all four `S171_*` markers. The console wrapper was PID
`36336` and the verified child image was PID `31048`. The wrapper exited `0`;
the child exit was not retained independently, so it remains `UNKNOWN` in the
derived result. CDB `10.0.29617.1000` attached to PID `31048` and returned
`2147942430` (`0x8007001e`), not success. The coordinator's subsequent CIM
query saw no Godot/CDB process. The helper's own cleanup flags are weaker:
its query-error handler returns False, and it retained neither child start
time nor checked Job/native-handle closure evidence.

Actual full-line breakpoint hits and the runtime PID/module record establish
that the child was inspected. The raw booleans alone are insufficient because
they also match echoed commands. Htrace reported OPEN entries for `0x464`
and `0x3f8`; neither is bound to the sentinel file or to the S153/S156 growth.
No stack address/module offset was captured. Missing PDB is an observed
limitation, not a demonstrated cause of that missing stack.

This corrects the S171 wrapper-PID limitation. It proves neither ownership,
leak nor root cause and does not justify a formal retry. Attribution remains
diagnostic, not an additional GT06 acceptance gate.

## Preservation and next action

`verify_s179.py` reads existing raw only and rejects wrapper PID, runtime PID
mismatch, wrong image and echoed commands. `derived-validation.json` retains
the unknown child exit and failed CDB exit. The original result is unchanged.
The executed helper is preserved as `executed-run_s179.py.txt`; do not execute
it again because it reuses IDs and overwrites files. Four path-preflight
failures before engine launch and the initial copy-command mistake are
coordinator observations; they have no successful engine receipt.

Two accidentally copied root files were byte-identical to the retained fixture
and removed: main.gd SHA256 fe8585deadd6a1f66828a801523dcbc32680c43a1a7fc2a7da9148d27212da85;
project.godot SHA256 e236bab2e49006547156c9764f4b154bfc851506b8a6747a421bad4d441a0200.
No other untracked files or prior evidence were removed.

Do not repeat this htrace hypothesis. A distinct API entry/return stack-capture
route may be prepared statically only after proving correct process lifetime
binding, exact exports, finite output and detach/cleanup. It needs a fresh ID
and does not require an assumption that Godot symbols will be available.

Primary references: [Godot console wrapper](https://github.com/godotengine/godot/blob/4.7.2-stable/platform/windows/console_wrapper_windows.cpp),
[CDB process attachment](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/debugging-a-user-mode-process-using-cdb),
[htrace process context](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/-htrace).
