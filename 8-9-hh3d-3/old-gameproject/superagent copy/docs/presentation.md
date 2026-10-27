# Classic presentation lane

This document describes the current original VFX/SFX slice. It is not a Y8
parity claim and it is not part of the deterministic `MatchSession` state.

`MatchSession` owns gameplay and emits immutable shot, explosion, prop, weapon
and fire rows. `game/presentation/arena_fx.gd` consumes those rows after the
state commit and draws short-lived tracers, muzzle flashes, impact rings,
sparks, debris, fire and pickup pulses. `game/presentation/combat_audio.gd`
generates small self-authored mono 16-bit WAV streams at runtime and routes
them through a positional `SFX` bus. The event cursor prevents one sound or
burst from being replayed on every TTL frame; a four-event-per-tick signal
budget, 24 active audio voices and 128-effect cap keep the lane bounded. If a
future simulation row supplies an `event_id`, it is preferred for
deduplication; the current fallback derives a stable identity from immutable
row fields.

Impact, prop-destruction and explosion rows also emit a bounded camera
impulse; `MatchRoom` decays it independently of the fixed-step state. The arena
shell adds authored skyline, light shafts and floor depth bands with CanvasItem
draw, so the Compatibility path has readable depth without a shader or
imported texture dependency.

`game/presentation/hud_bars.gd` adds view-only health, stamina and ammo meters
under the existing player panels. It derives ratios from the snapshot, marks
burning and bullet-time state visually, and contains no input or gameplay
authority.

The current renderer is Godot Compatibility. The presets therefore use
procedural `CanvasItem` drawing and remain visible on Web/mobile fallback paths;
they do not depend on `GPUParticles2D.emit_particle()`, which is unavailable in
Compatibility. A later art pass may add authored `CPUParticles2D` or sprite
flipbooks, but it must preserve the same event boundary, caps and fallback.

The official Godot references used for this design are:

- `GPUParticles2D` and `CPUParticles2D` for the capability split:
  https://docs.godotengine.org/en/stable/classes/class_gpuparticles2d.html
- `AudioStreamPlayer2D` for positional 2D playback:
  https://docs.godotengine.org/en/stable/classes/class_audiostreamplayer2d.html
- audio streams and Web playback guidance:
  https://docs.godotengine.org/en/stable/tutorials/audio/audio_streams.html

The short smoke test is `tests/presentation_fx.gd`; it checks event
deduplication, generated PCM and snapshot immutability. It does not compare
pixels or claim visual/audio similarity to the reference.
