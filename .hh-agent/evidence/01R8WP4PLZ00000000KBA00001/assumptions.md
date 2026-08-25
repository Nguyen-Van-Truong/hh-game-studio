# Assumptions — R8-WP4 polish

Run: `01R8WP4PLZ00000000KBA00001`

Filled from plan §6.2 (Godot 4.7.1-stable conventions, easiest to test,
fewest dependencies, then player-facing quality). Not E1–E4.

1. ColorRect `Body` nodes stay in the tree as invisible colliders.
   They are not a pass condition in `player.gd`. Sprites are the
   playfield look. CollisionShape2D stays enabled. HUD/menus may use
   ColorRect chrome. This keeps the graybox loop (`run_all.gd`) testable.
2. Relic-reached stays the only win flag. Key pickup and door-open
   still persist flags and never set win.
3. Art/audio are the R8-WP3 pin (`55d8f5c`). No new shipped PNG/WAV.
   Lantern textures are runtime `GradientTexture2D`, not extra art.
4. Settings (Master/Music/SFX volume, fullscreen) are session-only.
   They do not change save schema v1.
5. Fullscreen calls `DisplayServer.window_set_mode`. Official polish
   stays windowed; the in-game flag is still asserted.
6. Headless 4.7.1-stable uses the dummy renderer. Viewport.get_image()
   / texture_2d_get cannot stamp VISUAL there. Official polish on
   Windows launches non-headless (plan §7.3 UI-visible), resizes the
   borderless window to 1280x720, 1920x1080, and 854x480, asserts
   DisplayServer.window_get_size matches, and captures the live
   viewport. No SubViewport fallback. No content-scale blit of one
   designed frame onto another size. Camera zoom fills the designed
   vault height (854 is a tighter crop). A designed indigo backdrop
   replaces engine-clear (76,76,76). HUD is laid out on the playfield
   screen rect. This is official verify, not G5 human dogfood.
7. Screenshot review rejects engine-clear share >= 0.45 (catches 0.60),
   HUD sitting on letterbox void, and three near-identical center crops
   passed off as three layouts. Live hashes may drift; composition
   invariants are the pin, not bit-exact SHA.
8. INPUT injects InputEventKey and InputEventJoypadButton via
   Input.parse_input_event. After the key, door / relic / win / lose
   stay on production GameSession._physics_process (test_driven=false).
   Joy South (JOY_BUTTON_A) is read from Input as interact. App pause
   listener is PROCESS_MODE_ALWAYS so Esc/Start unpause while paused.
9. Official verify is `python tests/bootstrap/test_kho_bi_an_polish.py`
   exit 0. Import `--editor --import --quit` is retried; a -1 quit
   after a already-imported `.godot` tree is accepted. A Python FAIL
   does not overwrite hashes/shots. Kill leftover Godot on kho-bi-an
   first. Sequential only. Graybox Python harness stays valid for
   CURRENT_VALID_WP R8-WP4+.
10. `--provider plan` is unused. No API key. No remote imagegen.
11. G5 stays [ ]. This WP does not start R8-WP5 and does not claim
    human dogfood acceptance.
12. `src/` must not contain the word PLACEHOLDER in ids, paths, or
    strings. Filename-only scan is not enough.
