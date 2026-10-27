# Superagent art prototype

This directory contains original, procedural prototype presentation only. The
first Classic fighter is drawn by `game/fighter/fighter_view.gd` from the
state-to-pose profile in `game/fighter/fighter_visual_profile.gd`; it does not
copy a sprite, screenshot, audio, layout or code from the reference game.

The presenter keeps the authored `char_height=55.2` tuning and shortens only
the visible low poses for roll/dive/downed states. Gameplay collision and
simulation remain owned by the fixed 60 Hz state and physics bodies.

Every future imported asset must receive a row in `LICENSES.tsv` before it is
used by a scene.

The Classic match also has an original presentation layer: `game/presentation/arena_fx.gd`
draws short-lived tracers, sparks, rings, debris and fire from immutable match
events, while `game/presentation/combat_audio.gd` synthesizes small WAV SFX at
runtime. Both are outside the deterministic simulation and are kept deliberately
asset-free until a reviewed art/audio pass replaces or extends them.

The Relay Yard world pass in `game/ui/match_room.gd` is also procedural and
original: it draws kind-specific crate, barrel, glass, pickup and industrial
depth silhouettes from the immutable map snapshot. It is a readability slice,
not a claim of final pixel art or owner visual acceptance.

`backgrounds/relay_yard_backdrop.png` is an original OpenAI ImageGen backdrop
commissioned for this project on 2026-10-14. It is composited at low opacity
behind the procedural geometry; it contains no characters, UI, reference-game
art or gameplay state. The source prompt/output path is retained in the task
record, and the provenance row is in `LICENSES.tsv`.

The `characters/courier/` and `characters/mechanic/` folders contain two
original transparent 4×4 pose-sheet pilots generated for this project on
2026-10-14. Their `visual.json` files are the canonical region/pose sidecars.
`game/fighter/fighter_pose_sheet.gd` validates and loads those sidecars at runtime
so the shared `FighterView` adapter has one source for pivots and clip cadence. They are deliberately a
runtime proof package: editable layered authoring sources, left-facing redraws,
and weapon-specific hand anchors remain open work for the final SA-10 art gate.
