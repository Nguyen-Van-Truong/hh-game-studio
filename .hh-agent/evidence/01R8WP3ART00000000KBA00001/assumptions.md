# Assumptions — R8-WP3 art/audio/license

Run: `01R8WP3ART00000000KBA00001`

Filled from plan §6.2 (Godot 4.7.1-stable conventions, easiest to test,
fewest dependencies, then player-facing quality). Not E1–E4.

1. No remote imagegen. The machine is not authorized for a paid or
   keyed image API (E1/E2). Original procedural art is the brief
   fallback and is commercial-safe.
2. No third-party CC0/MIT URL is pinned because original procedural
   assets already satisfy the allowed license set. UNKNOWN is rejected.
3. ColorRect player/warden/items stay the playable colliders. Live
   TileMapLayer uses `res://assets/tiles/tileset_vault.png` (same
   collision). Wiring AnimatedSprite actors is R8-WP4.
4. Relic-reached stays the only win flag. Official art verify also
   re-runs `res://tests/run_all.gd` so the graybox loop stays testable.
5. Font remains the Godot 4.7.1-stable bundled Open Sans SemiBold
   (OFL 1.1). No second font file is shipped.
6. Music is a short original loop on the Music bus file, not autoplayed
   in the graybox session.
7. Contact sheet is an audit artifact (`assets/audit/`), not counted
   against the 16-art ship cap.
8. Official verify is plan §7.3 Godot CLI on `godot/dogfood/kho-bi-an`
   after killing leftover Godot on that --path. No sidecar. No addon.
9. `--provider plan` is unused. No API key.
10. Color-rect reject stays release / G5. This WP does not fake G5.
