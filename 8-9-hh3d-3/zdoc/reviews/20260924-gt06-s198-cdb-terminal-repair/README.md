# S198 CDB terminal-boundary repair

S197 proved the CDB attach and handle snapshot but stopped at `NtTerminateProcess` without a terminal capture. S198 used a fresh diagnostic ID and added an explicit `qd` after the debugger termination stop. CDB attached to the verified Godot PID, captured 256 handles, enabled `!htrace`, detached cleanly, and the target/helper/CDB all exited with the owned Job zero and closed. This remains diagnostic-only; GT06 gate, counter verifier, and acceptance status are unchanged.
