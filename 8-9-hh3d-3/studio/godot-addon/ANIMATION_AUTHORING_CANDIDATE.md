# O2 AnimationPlayer candidate

`animation_authoring.py` validates authority-0 animation-library proposals.
It binds an animation to a trusted `AnimationPlayer`, finite duration and loop
mode, closed node/property targets, strictly increasing key times and typed
2D/3D values. Rotation is scalar for 2D and a three component vector for 3D;
scale keys must stay positive. It derives node paths from the trusted node
tree and rejects stale project/scene revisions, duplicate tracks, foreign
players, malformed observed tracks and unknown fields.

The candidate does not edit Godot or issue an ACK. Native diagnostic
`o2-native-20260927-27` creates an `AnimationLibrary`, adds a position track,
checks library/track/key readback through do/undo/redo, then removes it. The
run passed with host exit 0, clean log, unchanged source/project snapshots and
358 checks. It remains authority 0; production lease rechecks, atomic save,
script policy and AUTH-01..05 isolation remain required.

Static verification:

```powershell
python -B -m unittest tests.godot.test_animation_authoring
```

This file does not enable the candidate profile or alter the accepted adapter.
