# S227 — retained identity exit observation

This Authority0 diagnostic exercises the cleanup boundary changed after S218.
An owned helper and its child are started by the existing bounded
`BenchmarkProcess`; an injected failure closes the owned Job, then reads the
child's exit code through the already identity-checked `ProcessProbe` handle
before releasing that handle. No Godot/Blender engine is started.

The probe recorded helper exit `2`, child PID `33896` exit `2`, the child's
Windows process-start identity, a zero/closed Job, and no retained handles.
The child exit is explicitly marked `natural_exit_not_inferred=true`; it is a
cleanup observation after the owner boundary, not a successful target receipt
and not GT06 acceptance. This closes the evidence gap where a helper's exit
was available but a killed child had no independent `process-exit.json`.

Raw evidence is retained in `studio/.local/reviews/gt06-s227-terminal-exit-01`
with manifest `9e4df4c1ea7ddfa82f2dc0c931435f7679bee64966dcf65d13debf34b865c8ff`
and archive
`034d230febc2f3d069f009623462af5e700e945d18c997e64ea3184b52f3574b`.
The formal gate, timeout, baseline, profile, counters, RSS threshold and
GT07–GT10 dependency are unchanged.
