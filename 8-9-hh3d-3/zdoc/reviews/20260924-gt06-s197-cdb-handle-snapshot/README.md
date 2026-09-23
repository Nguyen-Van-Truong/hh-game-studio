# S197 CDB handle snapshot

CDB attached to the verified Godot target and captured a `!handle 0 7` snapshot with 256 handles and enabled `!htrace`. The target emitted its completion marker, but the command script stopped at the process termination boundary, so the host driver could not capture an independently verified target exit before its bounded deadline. This is a harness terminal failure; preserve it and use a fresh ID with an explicit detach/continue command. The packet is diagnostic-only and does not change GT06.
