# S166 debugger handoff

`PLAN_HASH=7203d567ce822974d21364b6cd083ed64d30247e809533a78b021bbe154eb899`  
`SOURCE_HASH=fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde`  
`RUN_ID=gt06-s166-debugger-handoff-01`  
`COMMAND_ID=cmd.gt06.s166.debugger-handoff.1`  
`PASS=HANDOFF_READY_ONLY`  
`AUTHORITY=0`  
`PROCESS_EXIT=NOT_APPLICABLE`  
`BLOCKER=the host has no supported CDB/WinDbg binary`  
`NEXT_ACTION=provide an official Debugging Tools for Windows path, then run one bounded fixture attempt`

The read-only probe on 2026-09-22 found no `cdb.exe`, `windbg.exe`,
`windbgx.exe` or `ntsd.exe` under the standard Windows SDK and Visual Studio
roots, and no matching debugger process is running. The probe did not install,
stop or mutate any process.

When a supported debugger is available, the coordinator should verify the
absolute executable path and hash, keep the frozen source/profile/workstation,
use the S161 ready-before-open fixture, and run exactly one bounded attribution
attempt with a Windows Job Object and explicit host exit/cleanup capture. The
attempt must record `PLAN_HASH`, GT06 source closure, debugger hash, fixture
hash, `RUN_ID`, `COMMAND_ID`, actual target and helper exits, job/handle state,
and breakpoint/handle-owner observations. A clean debugger startup or a
successful fixture exit alone is not attribution and cannot open GT06.

Do not reuse S162–S165 identifiers, change vtable indices, run the formal
10×35 campaign, or promote this handoff to `AUTHORITY=1`. If the provided
debugger cannot expose creator/owner evidence, retain `UNKNOWN` and return to
the blocker report rather than changing gates or baseline.
