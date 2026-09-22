# S171 provenance and limitation notes

- Attempt directories are immutable and use fresh run/command IDs.
- Attempt-02 stopped at symbol loading; its target/CDB wrapper exits are UNKNOWN.
- Attempt-03, -05, and -06 reached the CDB attach/htrace command boundary and retained natural Godot exit `0`; the CDB process returned observed code `2147942430` after target termination. No forced cleanup flag was set in those receipts.
- Attempt-04 failed in harness preparation before any child process.
- `CreateFileW`, `NtCreateFile`, and `CreateFile2` breakpoint command markers were observed where listed, but `!htrace -diff` reported no outstanding handle in the integrated window and no concrete Godot module+offset caller was resolved. Breakpoint context is not ownership proof.
- `authority=0` for every receipt. This package cannot be used as GT06 full-run data, leak proof, root-cause proof, repair authorization, or acceptance.
