# S165 DbgEng process-selection attempt (AUTHORITY=0)

S165 continued the rejected S164 hypothesis by enumerating and selecting the
debuggee after `WaitForEvent`. It reused the owned S163 fixture source without
changing the stock engine, profile, gates, or workload. Compilation exited `0`;
the harness exited `1` with `process_count=0`. Because S165 still used the
incorrect indices from S164 (`WaitForEvent=90`, `Execute=63`), that observation
is not evidence that the real DbgEng path has no process list.

The complete Windows SDK vtable count confirms S163's `WaitForEvent=93` and
`Execute=66` values after including `Output`, `ControlledOutput`, and
`OutputPrompt` (`STDMETHODV`). S165 therefore remains a retained diagnostic
failure only: no fixture output, breakpoint placement, creator attribution,
leak/root-cause conclusion, or GT06 acceptance. Automatic retry is disabled.
