# O2 declarative gameplay behavior candidate

`gameplay_behavior.py` is a bounded, authority-0 state-machine contract for
small deterministic game behaviors. It accepts named states, input actions,
typed transitions and a fixed effect vocabulary (`move`, `jump`,
`set_velocity`, `face`, `emit_signal`, `play_animation`). It rejects script
text, expressions, paths, arbitrary method names, duplicate transitions,
invalid state graphs and non-finite/out-of-range values. Projections bind both
scene and project revisions and remain `runtime_authorized=false`.

The candidate does not execute code, create a Godot script, mutate a scene,
save, or issue an ACK. Native script boundary, deterministic dispatch,
sandbox/AUTH-05, readback and UndoRedo remain required before GT-09.

Static verification:

```powershell
python -B -m unittest tests.godot.test_gameplay_behavior
```

This file does not enable the candidate profile or alter the accepted adapter.
