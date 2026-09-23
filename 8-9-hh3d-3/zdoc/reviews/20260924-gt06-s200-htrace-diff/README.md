# S200 CDB htrace differential

S200 is a fresh bounded diagnostic after the S198 terminal-boundary repair. CDB attached to the verified Godot target, captured the handle table, enabled `!htrace`, ran `!htrace -diff`, and detached with target/helper/CDB exit 0 and Job cleanup verified. The diff reported 0x1e0d new stack traces and 0x6a displayed outstanding entries, but no resolved creator stack/module offset appears in the captured output. This remains Authority 0 and diagnostic-only: GT06, its counter gate, timeout, baseline, profile and acceptance contract are unchanged.
