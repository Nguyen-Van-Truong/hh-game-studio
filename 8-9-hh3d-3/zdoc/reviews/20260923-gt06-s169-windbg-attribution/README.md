# S169 bounded CDB/htrace attribution fixture (AUTHORITY=0)

`gt06-s169-windbg-attribution-01` is the first bounded fixture after the
owner-authorized Microsoft.WinDbg installation. It attached CDB to the exact
fixture PID (`-p`, `-pd`, `-nosqm`), enabled `!htrace`, took a pre-open
snapshot, observed the open diff, took a post-open snapshot, observed the
close diff, disabled tracing, and captured natural exits for both target and
debugger. The target created one Event and one IoCompletion handle and closed
both. The raw htrace diff records the handle values plus the same TID/PID.

The first PowerShell 5.1 runner failed before CDB startup because the event
handler had no runspace. The first Python runner failed before attach because
the literal `no` after `-netsyms` was parsed as the debuggee path. These raw
harness boundaries are retained in the directory; the corrected Python
attempt is the one that produced `s169-attribution-result.json`.

The diff did not resolve a caller module/offset or an explicit creator stack.
Therefore this is diagnostic evidence only: `AUTHORITY=0`, attribution
`UNKNOWN`, excluded from F13/F14, the GT06 dataset, leak/root-cause claims,
repair authorization, and GT06 acceptance. No Godot/Blender engine ran.
