# O2 AnimationPlayer candidate

`animation_authoring.py` validates authority-0 animation-library proposals.
It binds an animation to a trusted `AnimationPlayer`, finite duration and loop
mode, closed node/property targets, strictly increasing key times and typed
2D/3D values. Rotation is scalar for 2D and a three component vector for 3D;
scale keys must stay positive. It derives node paths from the trusted node
tree and rejects stale project/scene revisions, duplicate tracks, foreign
players, malformed observed tracks and unknown fields.

The candidate does not edit Godot or issue an ACK. The disposable native
diagnostic consumes its validated projections in `tests/godot/animation_native.gd`.
It constructs two clips with six tracks: 2D/3D position, rotation and scale,
different durations, and both loop modes. Track paths resolve relative to the
player's root. Playback uses `play`/manual `advance`, reads the actual node
properties at start/midpoint/end or loop wrap, and repeats after Undo/Redo.
The host independently checks raw keys, paths, sample times, values and request
bindings against the input recipe, with absolute numeric tolerance `1e-4`.
Negative tests reject wrong poses, stale bindings and missing/malformed rows
even when their native `passed` flags are true.

Run `o2-native-20260927-29` passed: 373 checks, host/wrapper exit 0, no timeout,
verified process tree, clean log and unchanged source/project snapshots.
Its 17-file source closure is
`25dc209c27a8f2140668520e9834c36461e4d67d0d0ec59add36d178ffc5bbba`.
Raw evidence stays at `C:/Users/truon/.codex/o2-native-20260927-29/`.
The combined O2 regression passed 147 tests (19 animation/evidence tests).

Earlier run `-27` only read a hardcoded track and did not prove playback;
its `../Actor:position` path was wrong for the default player root. Run `-28`
proved a single 2D midpoint, but lacked raw numeric verification and broader
track coverage. Both remain historical; `-29` is the current diagnostic.
This does not prove general animation authoring, public command integration,
production lease rechecks, atomic save/reload, script policy or AUTH-01..05
isolation. The separate gameplay-behavior module is not in this native closure.

Static verification:

```powershell
python -B -m unittest tests.godot.test_animation_authoring
```

This file does not enable the candidate profile or alter the accepted adapter.
