# O2 declarative gameplay behavior candidate

`gameplay_behavior.py` is a bounded, authority-0 state-machine contract for
small deterministic game behaviors. It accepts named states, input actions,
typed transitions and a fixed effect vocabulary (`move`, `jump`,
`set_velocity`, `face`, `emit_signal`, `play_animation`). Each effect has an
exact parameter schema; it rejects script text, expressions, paths, arbitrary
method names, duplicate transitions, invalid state graphs and
non-finite/out-of-range values. Projections bind both scene and project
revisions and remain `runtime_authorized=false`.

The candidate does not execute caller code, create a Godot script, save, or
issue an ACK. Disposable `tests/godot/behavior_native.gd` now interprets one
validated projection against a temporary `CharacterBody2D` without loading
GDScript. It checks a three-step move/jump/land sequence, typed effects,
repeatability, and actual node state after Undo/Redo. Host-side verification
compares raw snapshots and request bindings to the frozen recipe. Run
`o2-native-20260927-31` passed with 383 checks, actual host/wrapper exit 0,
clean log, verified process tree, and unchanged source/project snapshots;
source closure is `f548acd8dd3c5e17170a1d71898cb28196dd8898e015e2614a343e6899e87e83`.
This is still authority-0 diagnostic evidence. Native script execution,
production adapter integration, sandbox/AUTH-05, save/reload, public ACK,
and GT-09 mini-game acceptance remain required.

Static verification:

```powershell
python -B -m unittest tests.godot.test_gameplay_behavior
```

The combined O2 static regression is 149 tests passing. Run `-30` is retained
as failed compile evidence and was not reclassified as PASS.

This file does not enable the candidate profile or alter the accepted adapter.
