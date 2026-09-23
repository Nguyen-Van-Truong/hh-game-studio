# S178 — GT06 replay capability boundary

Date: 2026-09-23 (Asia/Saigon)
Authority: 0 (read-only decision memo; no engine run, no acceptance change)

## Decision

The current authenticated GT06 replay service has no supported entry point for
driving the S177 consumer-pilot project or for submitting a caller-owned input
trace. Do not add an adapter, subclass the fixed backend, or reinterpret the
pilot runtime as GT06 evidence. Keep the S177 pilot evidence and its
limitations unchanged.

## Evidence inspected

* `studio/host/replay/contract.py:22,52-74` exposes only `play.start`,
  `play.inspect`, and `play.capture`; `play.inspect` explicitly declares
  `live_supported: false`. The catalog describes launch of the fixed prepared
  immutable snapshot and capture labels declared by its trace.
* `studio/host/replay/service.py:33-40,145-186,213-223` requires the exact
  `PreparedPlay` type, validates the prepared binding, starts one prepared
  backend, and reads only a completed retained report. Stop and lookup are
  separate authenticated control routes (`:299-331`).
* `studio/host/replay/backend.py:34-86,99-125` prepares the accepted GT05
  inputs, `default_trace(seed)`, fixed speed `3.0`, and the pinned fixture
  project before any grant; it has one start and one irreversible Stop latch.
* `studio/host/replay/native_runner.py:73-125,172-195` binds the accepted
  manifest, installed source generation, fixed trace/configuration and fixture
  project. It rejects general scripts/configuration and alternate traces.
* `studio/host/replay/trace.py:200-225` defines the fixed 360-frame trace and
  its declared capture labels; it is not a live-input channel.

## Consequence

The S177 consumer pilot remains valid within its stated scope: authenticated
GT03/GT04 authoring plus the separate pinned Godot runtime evidence. It does
not prove GT06, and this memo does not add a GT06 gate or claim a leak/root
cause. A future GT06 diagnostic may proceed only after a genuinely new,
supported entry point or an owner-approved ADR changes the evidence contract.
Until then, do not reauthor or retry an unchanged S162–S177 route.

## Reproducibility

The inspected source was the current clean worktree at the S177 checkpoint.
No Godot, Blender, debugger, or benchmark process was running during this
read-only inspection. Source line references above are intentionally retained
so a later contract change can be compared without rerunning the engine.

## Inspected source hashes

```text
1df6a84cf58398b3dd438eed6c65ffe3660c5522c53842775d6b24baec676d6c  studio/host/replay/contract.py
d8d046ea2144ade026cce7e63a53b52885a28b213193fed19f932a773a9758a5  studio/host/replay/service.py
f7d22a7b3ff001f6fca175c11b5a94c7d75933ac8d3173be3323849af39f8169  studio/host/replay/backend.py
08ad9f82ecbaf26cb37cad970599b51032860cc7241af838d6b9ac335f4ff72f  studio/host/replay/native_runner.py
8037b87d3a4ac51afc5504ac3105362f0211fa1519e68de32a32489166e9aaf5  studio/host/replay/trace.py
```
