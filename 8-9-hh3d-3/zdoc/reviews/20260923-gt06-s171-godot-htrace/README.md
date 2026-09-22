# S171 bounded Godot/CDB htrace diagnostic (AUTHORITY=0)

This package records one bounded integrated Godot diagnostic with five fresh attempt IDs. It never ran the formal GT06 campaign and is excluded from F13/F14, the GT06 dataset, leak proof, root-cause claims, repair authorization, and acceptance.

- `attempt-02`: Godot reached all markers, but CDB stalled in `.reload /f` before `CDB_ATTACHED`; the owned runner, CDB, and Godot were stopped at the finite timeout.
- `attempt-03`: CDB attached and enabled `!htrace`; Godot exit was 0. `CreateFileW` did not break and the diff had no outstanding handle.
- `attempt-04`: harness copy error before launch; retained as an attempt-inventory gap, with no engine/debugger process.
- `attempt-05`: CDB attached, `NtCreateFile`/`CreateFile2`/`CloseHandle` breakpoints were installed, Godot exit was 0, but no outstanding handle or module/offset attribution was observed; CDB returned `2147942430`.
- `attempt-06`: same bounded discriminator with a 20-second pre-open and 15-second hold; CDB attached and htrace enabled, Godot exit was 0, but no outstanding handle or owner module/offset was observed; CDB returned `2147942430`.

All attempts use the pinned Godot 4.7.2 console binary, the unchanged source/profile pins, and separate output folders. This closes the useful integrated diagnostic boundary for the current environment; GT06 remains `IN_PROGRESS` with zero accepted full runs. The next step is external ownership/debug-symbol evidence or a separately provided supported attribution integration, followed by the original 10 fresh host/editor pairs × 35 batches and two same-hash critics.
