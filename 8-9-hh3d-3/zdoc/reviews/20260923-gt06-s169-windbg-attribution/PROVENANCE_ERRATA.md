# S169 provenance errata

The directory is retained as a diagnostic packet, but it is **not** a
single-attempt immutable execution archive. The PowerShell 5.1 runner failed
before CDB startup, the PowerShell 7 runner raised a runspace exception, and
two early Python attempts timed out at the attach marker while using the bad
`-netsyms no` argument. Their individual stdout/stderr/exit receipts were not
sealed before the final corrected Python attempt reused the flat output names.

Therefore `ATTEMPT_COLLISION=1`, `PROVENANCE_PARTIAL=1`, and the wrapper exit
for the early attempts is `UNKNOWN`. The only attributable final payload is
the output whose receipt reports target PID 44460 and CDB/target exits 0; the
earlier attempts are preserved here only as known harness history and must not
be merged into the final run. The final payload remains `AUTHORITY=0` and
diagnostic-only. A future run requires a fresh immutable directory and fresh
RUN_ID/COMMAND_ID, even if the source and debugger are unchanged.
