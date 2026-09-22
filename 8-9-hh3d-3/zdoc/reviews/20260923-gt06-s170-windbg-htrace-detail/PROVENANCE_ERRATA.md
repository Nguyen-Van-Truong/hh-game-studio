# S170 provenance and attribution errata

The final S170 target/CDB exits are both 0 and no forced cleanup was needed.
The packet is nevertheless diagnostic-only. The command file queried fixed
`0x30c`/`0x310` values; the target JSON records the actual values as
`0x2fc`/`0x300` for the two retained handles, so those per-handle queries are
not a dynamically bound complete check. The all-traces query still records
the correct target PID/TID and OPEN/CLOSE history. `!handle` returned Win32
error 6 after the handles had been closed.

The receipt's generic `KERNELBASE!`/`ntdll!` text is debugger stop context,
not a resolved creator stack. The corrected interpretation is
`caller_module_offset_resolved=false`, `per_handle_query_resolved=false`,
`attribution=UNKNOWN`, `AUTHORITY=0`. Do not use S170 to authorize a formal
GT06 run, claim a leak/root cause, or substitute for an S160-integrated owned
Godot/editor attribution attempt.
