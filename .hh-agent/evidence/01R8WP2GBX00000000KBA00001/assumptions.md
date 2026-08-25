# Assumptions — R8-WP2 graybox

Run: `01R8WP2GBX00000000KBA00001`

Filled from plan §6.2 (Godot 4.7.1-stable conventions, easiest to test,
fewest dependencies, then player-facing quality). Not E1–E4.

1. Dogfood lives at `godot/dogfood/kho-bi-an/`. Not `plugin-project/snake/`,
   not r7w6 trials, not stock-poc.
2. `scenes/main.tscn` only attaches `App`. The vault tree is built in typed
   GDScript so ColorRect graybox stays the visible stand-in.
3. Official verify is plan §7.3 Godot CLI:
   `godot --headless --path godot/dogfood/kho-bi-an --script res://tests/run_all.gd`
   after import. GUT 9.7.1 is pinned but not copied into this game (brief:
   no addon in the export tree). `run_all.gd` is the stock runner CM-154 names.
4. No sidecar / MCP Play: the dogfood project has no `hh_agent` addon.
   `--provider plan` is unused. No API key.
5. Win predicate is `relic_reached` only. Key pickup and door-open persist
   flags and never set win.
6. Stretch aspect is `keep` (brief), not the matrix `expand` example.
7. Save schema v1 is `user://kho_bi_an_v1.cfg` via ConfigFile. Tests use
   `user://kho_bi_an_r8wp2_test.cfg`.
8. Color-rect reject stays release / G5. This WP does not ship final art
   and does not start R8-WP3.
9. Relic room begins strictly east of the door column. The door tile is
   room_id "door", not "relic". Continue after door-open restores the
   saved start-side room and does not teleport to RELIC_ENTER.
10. Relic interact requires door_open. Closed-door relic interact does
    not set relic_reached. Official LOOP fail-closes that case first,
    then walks start→key→door→relic→win.
11. SAVE_LOAD persists key+door+start room, Continue, then walks the
    rest of the path to relic and win. room_id is asserted.
12. Warden patrols the door-room north floor (y=6) so a vault-floor walk
    can be touched. Lose+restart stays. Off-path y=3 suicide is gone.
13. Official driver stays step_fixed (A13). ColorRects stay. relic_reached
    remains the only win flag. WIN_FLAG proves interact, not a field poke.
