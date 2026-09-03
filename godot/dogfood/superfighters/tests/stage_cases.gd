class_name StageCases
extends RefCounted

## VF6-WP3 stage campaign. Official proof is title clicks plus
## live catalog-map melee (rooftops → storage → police → hazardous).
## No Close Clinch skin-swap. No apply_eval rematch. No pit suicide.
## Bots stay smoke. Survival is not a Stage arena; Title Survival is shipped separately. Tiers are approximation.

const _Stage: GDScript = preload("res://src/sim/stage.gd")
const RUN_ID := "VF6WP3-20260901-ASIA-SAIGON-03"

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var used_force_kill: int = 0
static var used_teleport: int = 0
static var used_apply_eval: int = 0
static var outcome_schema: Dictionary = {}
static var outcome_load: Dictionary = {}
static var outcome_advance: Dictionary = {}
static var outcome_loss: Dictionary = {}
static var outcome_hash: Dictionary = {}
static var outcome_continue: Dictionary = {}
static var outcome_reset: Dictionary = {}
static var outcome_live: Dictionary = {}
static var still_paths: Dictionary = {}
static var timeline: Array = []
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var events_all: Array = []
static var load_rows: Array = []
static var live_app: App = null
static var win_rows: Array = []
static var police_cross: int = 0


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	used_force_kill = 0
	used_teleport = 0
	used_apply_eval = 0
	outcome_schema = {"verdict": "unproven"}
	outcome_load = {"verdict": "unproven"}
	outcome_advance = {"verdict": "unproven"}
	outcome_loss = {"verdict": "unproven"}
	outcome_hash = {"verdict": "unproven"}
	outcome_continue = {"verdict": "unproven"}
	outcome_reset = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	still_paths = {}
	timeline = []
	snapshot_start = {}
	snapshot_end = {}
	events_all = []
	load_rows = []
	win_rows = []
	live_app = app
	_Stage.reset_progress()
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_contract())
	print("HH_VF_STAGE STEP=hash")
	_append(errors, reward_hash_stable())
	print("HH_VF_STAGE STEP=load")
	_append(errors, await load_roster(app))
	print("HH_VF_STAGE STEP=title_loss")
	_append(errors, await title_and_loss(app))
	print("HH_VF_STAGE STEP=advance")
	_append(errors, await win_advances(app))
	print("HH_VF_STAGE STEP=continue_reset")
	_append(errors, await continue_and_reset(live_app if live_app != null else app))
	_append(errors, _require_outcomes())
	return errors


static func schema_contract() -> PackedStringArray:
	var errors: PackedStringArray = _Stage.validate()
	var payload: Dictionary = _Stage.data()
	if bool(payload.get("survival_shipped", false)):
		errors.append("stage campaign must not ship Survival as a Stage arena")
	if not bool(payload.get("title_survival_shipped", false)):
		errors.append("stage catalog must acknowledge Title Survival is shipped")
	if str(payload.get("order_class", "")) != "approximation":
		errors.append("stage order must stay approximation")
	outcome_schema = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"source": "data/sim/stage.json",
		"order_class": str(payload.get("order_class", "")),
		"tier_class": str(payload.get("difficulty_class", "")),
		"y8_order_observed": bool(payload.get("y8_order_observed", true)),
	}
	return errors


static func reward_hash_stable() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	_Stage.reset_progress()
	var first: Dictionary = _Stage.record_win(0)
	var h1: String = str(first.get("reward_hash", ""))
	var again: Dictionary = _Stage.record_win(0)
	var h1b: String = str(again.get("reward_hash", ""))
	if h1 == "" or h1 != h1b:
		errors.append("HASH first-win must be stable on duplicate award")
	if int(again.get("score", 0)) != int(first.get("score", 0)):
		errors.append("HASH duplicate win must not add score")
	if int(again.get("current_index", -1)) != 1:
		errors.append("HASH first win must checkpoint index 1")
	var second: Dictionary = _Stage.record_win(1)
	var h2: String = str(second.get("reward_hash", ""))
	if h2 == "" or h2 == h1:
		errors.append("HASH second distinct win must change hash")
	_Stage.reset_progress()
	var replay: Dictionary = _Stage.record_win(0)
	_Stage.record_win(1)
	var replay2: Dictionary = _Stage.load_or_empty()
	if str(replay.get("reward_hash", "")) != h1:
		errors.append("HASH replay of first win must match")
	if str(replay2.get("reward_hash", "")) != h2:
		errors.append("HASH replay of two-win sequence must match")
	_Stage.reset_progress()
	var skipped: Dictionary = _Stage.record_win(3)
	var skip_disk: Dictionary = _Stage.load_or_empty()
	if (
		_Stage.last_error == ""
		or int(skipped.get("current_index", -1)) != 0
		or int(skip_disk.get("score", -1)) != 0
		or not _array(skip_disk.get("awarded", [])).is_empty()
		or _Stage.last_save_path != ""
	):
		errors.append("HASH record_win must fail-closed on a skipped index")
	_Stage.reset_progress()
	var first_ok: Dictionary = _Stage.record_win(0)
	if _Stage.last_error != "" or _Stage.last_save_path == "":
		errors.append("HASH persist must return a path and leave last_error empty")
	var rel: String = _Stage.store_rel()
	var abs_final: String = ProjectSettings.globalize_path(rel)
	var abs_bak: String = abs_final + ".bak"
	if not FileAccess.file_exists(rel + ".bak"):
		errors.append("HASH persist must keep parked .bak after a successful write")
	if FileAccess.file_exists(rel):
		DirAccess.copy_absolute(abs_final, abs_bak)
		DirAccess.remove_absolute(abs_final)
	var recovered: Dictionary = _Stage.load_or_empty()
	if str(recovered.get("reward_hash", "")) != str(first_ok.get("reward_hash", "")):
		errors.append("HASH load must recover parked .bak after a missing final")
	outcome_hash = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"hash_win0": h1,
		"hash_win0_dup": h1b,
		"hash_win1": h2,
		"source": "StageRules.record_win idempotent + sequence replay + fail-closed persist + kept bak",
	}
	_Stage.reset_progress()
	return errors


static func load_roster(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var ids: PackedStringArray = _Stage.arena_ids()
	var i: int = 0
	var ok: bool = ids.size() == 4
	while i < ids.size():
		var mid: String = String(ids[i])
		app.start_fight("stage", mid, i)
		await SimReplay.sync_physics(app)
		var session: GameSession = app.session
		var bots: int = 0
		if session != null:
			bots = session.live_bot_count()
		var want_bots: int = _Stage.bot_count(i)
		var row: Dictionary = {
			"index": i,
			"map_id": mid,
			"loaded": session != null and session.map_id == mid,
			"bots": bots,
			"want_bots": want_bots,
			"tier": _Stage.tier_id(i),
			"tier_class": "approximation",
			"live_is_bot": _count_is_bot(session),
		}
		load_rows.append(row)
		_note("load", session, row)
		if session == null or session.map_id != mid or session.mode != "stage":
			errors.append("LOAD stage %d map %s missing" % [i, mid])
			ok = false
		if bots != want_bots or _count_is_bot(session) != want_bots:
			errors.append("LOAD stage %d bots=%d want=%d" % [i, bots, want_bots])
			ok = false
		i += 1
	if DisplayServer.get_name() != "headless" and still_paths.get("load", "") == "":
		still_paths["load"] = await _capture_still(app, "stage_load")
	outcome_load = {
		"verdict": "pass" if ok else "fail",
		"rows": load_rows,
		"source": "start_fight catalog maps; live is_bot actors; no force_kill",
	}
	return errors


static func title_and_loss(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	_Stage.reset_progress()
	app.restart_to_title()
	await _ui_frames(app)
	still_paths["title"] = await _capture_still(app, "stage_title")
	_append(errors, await _title_start_stage(app))
	var session: GameSession = app.session
	if session == null or session.map_id != "rooftops" or session.stage_index != 0:
		errors.append("TITLE Stage must load rooftops index 0")
		outcome_loss = {"verdict": "fail", "source": "title Stage missed rooftops"}
		return errors
	still_paths["fight"] = await _capture_still(app, "stage_fight")
	if snapshot_start.is_empty() and session != null:
		snapshot_start = session.snapshot()
	_note("fight_start", session, {"reason": "official_loss"})
	var hash_before: String = str(_Stage.load_or_empty().get("reward_hash", ""))
	var idx_before: int = app.stage_index
	var bot_hp0: float = _first_bot_hp(session)
	var fight: Dictionary = await _catalog_resolve(app, "lose")
	session = app.session
	var p1: Fighter = session.player1() if session != null else null
	var death_cause: String = p1.death_cause if p1 != null else ""
	var bot_hp: float = _first_bot_hp(session)
	var bot_alive: bool = _first_living_foe(session) != null
	var lost: bool = (
		session != null
		and session.outcome == "lose"
		and session.map_id == "rooftops"
		and death_cause == "damage"
		and app.lose_screen != null
		and app.lose_screen.visible
		and bool(fight.get("ok", false))
	)
	if not lost:
		errors.append(
			"LOSS rooftops must be damage KO got outcome=%s cause=%s map=%s bot_hp=%s"
			% [
				str(session.outcome if session != null else ""),
				death_cause,
				str(session.map_id if session != null else ""),
				str(bot_hp),
			]
		)
	still_paths["lose"] = await _capture_still(app, "stage_lose")
	_note("loss", session, {
		"death_cause": death_cause,
		"end_reason": session.match_rules.end_reason if session != null and session.match_rules != null else "",
		"bot_hp": bot_hp,
		"bot_hp0": bot_hp0,
		"bot_alive": bot_alive,
	})
	if app.lose_screen != null and app.lose_screen.rematch_btn != null:
		await _activate_button(app, app.lose_screen.rematch_btn, "rematch")
		await SimReplay.sync_physics(app)
	session = app.session
	var stayed: bool = (
		session != null
		and session.mode == "stage"
		and session.map_id == "rooftops"
		and session.stage_index == 0
		and idx_before == 0
		and session.outcome == "play"
	)
	var hash_after: String = str(_Stage.load_or_empty().get("reward_hash", ""))
	if not stayed:
		errors.append(
			"LOSS rematch skipped/duped map=%s idx=%d"
			% [str(session.map_id if session != null else ""), app.stage_index]
		)
	if hash_after != hash_before:
		errors.append("LOSS rematch must not change reward hash")
	_note("rematch", session, {"after_loss": true, "hash": hash_after})
	if session != null:
		_note("post_rematch_snap", session, {"hash": session.snapshot_hash()})
	outcome_loss = {
		"verdict": "pass" if lost and stayed and hash_after == hash_before else "fail",
		"lost": lost,
		"stayed_map": session.map_id if session != null else "",
		"stayed_index": app.stage_index,
		"death_cause": death_cause,
		"end_reason": session.match_rules.end_reason if session != null and session.match_rules != null else "",
		"bot_hp": bot_hp,
		"bot_hp0": bot_hp0,
		"pit_loss": 0,
		"hash_before": hash_before,
		"hash_after": hash_after,
		"source": "title Stage rooftops + live bot melee damage KO + Rematch button stays index 0",
	}
	return errors


static func win_advances(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	_Stage.reset_progress()
	_append(errors, await _title_start_stage(app))
	if app.session == null or app.session.map_id != "rooftops":
		errors.append("ADVANCE title Stage must start rooftops")
		outcome_advance = {"verdict": "fail"}
		return errors
	_append(errors, await _win_on_catalog(app, 0, "rooftops", "storage"))
	var after0: GameSession = app.session
	var after0_map: String = after0.map_id if after0 != null else ""
	var after0_idx: int = after0.stage_index if after0 != null else -1
	var after0_bots: int = after0.live_bot_count() if after0 != null else -1
	var progress0: Dictionary = _Stage.load_or_empty()
	var ok0: bool = (
		after0 != null
		and after0_map == "storage"
		and after0_idx == 1
		and after0_bots == _Stage.bot_count(1)
		and int(progress0.get("current_index", -1)) == 1
		and int(progress0.get("score", 0)) == _Stage.score_for(0)
	)
	if not ok0:
		errors.append(
			"ADVANCE win0 map=%s idx=%d bots=%s score=%s"
			% [
				after0_map,
				after0_idx,
				str(after0_bots),
				str(progress0.get("score", -1)),
			]
		)
	still_paths["advance"] = await _capture_still(app, "stage_advance")
	var h0: String = str(progress0.get("reward_hash", ""))
	_append(errors, await _win_on_catalog(app, 1, "storage", "police"))
	var after1: GameSession = app.session
	var after1_map: String = after1.map_id if after1 != null else ""
	var after1_idx: int = after1.stage_index if after1 != null else -1
	var progress1: Dictionary = _Stage.load_or_empty()
	var h1: String = str(progress1.get("reward_hash", ""))
	var ok1: bool = (
		after1 != null
		and after1_map == "police"
		and after1_idx == 2
		and int(progress1.get("current_index", -1)) == 2
		and h1 != h0
	)
	if not ok1:
		errors.append(
			"ADVANCE win1 map=%s idx=%d hash_changed=%s"
			% [after1_map, after1_idx, str(h1 != h0)]
		)
	var hash_mid: String = h1
	var rematch_map: String = ""
	if after1 != null and after1.map_id == "police":
		_note("midrun_loss_start", after1, {})
		var mid: Dictionary = await _catalog_resolve(app, "lose")
		var lost_session: GameSession = app.session
		var mid_cause: String = ""
		if lost_session != null and lost_session.player1() != null:
			mid_cause = lost_session.player1().death_cause
		var mid_ok: bool = (
			lost_session != null
			and lost_session.outcome == "lose"
			and lost_session.map_id == "police"
			and lost_session.stage_index == 2
			and mid_cause == "damage"
			and bool(mid.get("ok", false))
		)
		if not mid_ok:
			errors.append(
				"ADVANCE mid-loss must be police damage KO got map=%s outcome=%s cause=%s"
				% [
					str(lost_session.map_id if lost_session != null else ""),
					str(lost_session.outcome if lost_session != null else ""),
					mid_cause,
				]
			)
		if app.lose_screen != null and app.lose_screen.visible and app.lose_screen.rematch_btn != null:
			await _activate_button(app, app.lose_screen.rematch_btn, "rematch")
			await SimReplay.sync_physics(app)
		var rematch: GameSession = app.session
		rematch_map = rematch.map_id if rematch != null else ""
		hash_mid = str(_Stage.load_or_empty().get("reward_hash", ""))
		var stayed: bool = (
			rematch != null
			and rematch.map_id == "police"
			and rematch.stage_index == 2
			and rematch.outcome == "play"
			and hash_mid == h1
		)
		if not stayed:
			errors.append(
				"ADVANCE mid-loss rematch map=%s idx=%d"
				% [rematch_map, app.stage_index]
			)
		_note("midrun_rematch", rematch, {
			"hash": hash_mid,
			"snap": rematch.snapshot_hash() if rematch != null else "",
		})
	_append(errors, await _win_on_catalog(app, 2, "police", "hazardous"))
	var after2: GameSession = app.session
	var after2_map: String = after2.map_id if after2 != null else ""
	var after2_idx: int = after2.stage_index if after2 != null else -1
	var after2_bots: int = after2.live_bot_count() if after2 != null else -1
	var progress2: Dictionary = _Stage.load_or_empty()
	var h2: String = str(progress2.get("reward_hash", ""))
	var reached_haz: bool = (
		after2 != null
		and after2_map == "hazardous"
		and after2_idx == 3
		and after2.outcome == "play"
		and after2_bots == _Stage.bot_count(3)
		and _count_is_bot(after2) == _Stage.bot_count(3)
		and int(progress2.get("current_index", -1)) == 3
		and not bool(progress2.get("cleared", true))
	)
	if not reached_haz:
		errors.append(
			"ADVANCE win police must load hazardous bots=%s idx=%d map=%s"
			% [str(after2_bots), after2_idx, after2_map]
		)
	if DisplayServer.get_name() != "headless":
		still_paths["hazardous"] = await _capture_still(app, "stage_hazardous")
	_note("hazardous_reach", after2, {
		"bots": after2_bots,
		"hash": h2,
		"snap": after2.snapshot_hash() if after2 != null else "",
	})
	if after2 != null:
		snapshot_end = after2.snapshot()
	outcome_advance = {
		"verdict": "pass" if ok0 and ok1 and reached_haz and errors.is_empty() else "fail",
		"after_win0_map": after0_map,
		"after_win1_map": after1_map,
		"after_win2_map": after2_map,
		"rematch_map": rematch_map,
		"hash_win0": h0,
		"hash_win1": h1,
		"hash_win2": h2,
		"hash_after_loss": hash_mid,
		"win_rows": win_rows,
		"reached_maps": ["rooftops", "storage", "police", "hazardous"],
		"source": "title Stage + live catalog melee KO; win police loads hazardous; rematch is button",
	}
	if str(outcome_hash.get("verdict", "")) != "fail" and h0 != "" and h1 != "" and hash_mid == h1:
		outcome_hash["live_hash_win0"] = h0
		outcome_hash["live_hash_win1"] = h1
		outcome_hash["live_hash_win2"] = h2
		outcome_hash["live_hash_after_loss"] = hash_mid
	return errors


static func continue_and_reset(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var before: Dictionary = _Stage.load_or_empty()
	var want_idx: int = int(before.get("current_index", 0))
	var want_map: String = _Stage.map_at(want_idx)
	if want_map == "rooftops" or want_idx <= 0:
		errors.append("CONTINUE checkpoint must be a mid-run map, not rooftops")
	var tree: SceneTree = app.get_tree() if app != null else null
	if tree == null:
		errors.append("CONTINUE missing tree for cold reload")
		outcome_continue = {"verdict": "fail"}
		return errors
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	app.shutdown()
	app.queue_free()
	await tree.process_frame
	await tree.process_frame
	var fresh: App = packed.instantiate() as App
	fresh.test_driven = true
	tree.root.add_child(fresh)
	live_app = fresh
	await _ui_frames(fresh)
	if fresh.title != null:
		fresh.title.refresh_stage_caption()
	still_paths["continue_title"] = await _capture_still(fresh, "stage_continue")
	_append(errors, await _title_start_stage(fresh))
	var session: GameSession = fresh.session
	var continued: bool = (
		session != null
		and session.map_id == want_map
		and session.stage_index == want_idx
		and session.map_id != "rooftops"
		and session.mode == "stage"
		and session.live_bot_count() == _Stage.bot_count(want_idx)
	)
	if not continued:
		errors.append(
			"CONTINUE cold title loaded %s idx=%d want %s idx=%d"
			% [
				str(session.map_id if session != null else ""),
				fresh.stage_index,
				want_map,
				want_idx,
			]
		)
	_note("cold_continue", session, {
		"want_map": want_map,
		"want_index": want_idx,
		"snap": session.snapshot_hash() if session != null else "",
	})
	var haz_win: Dictionary = {}
	if continued and session != null and session.map_id == "hazardous":
		_append(errors, await _win_on_catalog(fresh, 3, "hazardous", "hazardous"))
		haz_win = _Stage.load_or_empty()
	outcome_continue = {
		"verdict": "pass" if continued else "fail",
		"map_id": session.map_id if session != null else "",
		"stage_index": fresh.stage_index,
		"cold": true,
		"cleared_after_haz": bool(haz_win.get("cleared", false)),
		"source": "write save + free App + cold instantiate + title Continue Stage",
	}
	fresh.restart_to_title()
	await _ui_frames(fresh)
	if fresh.title == null or fresh.title.reset_stage_btn == null:
		errors.append("RESET missing Reset Stage")
		outcome_reset = {"verdict": "fail"}
		return errors
	var vs_label: String = str(fresh.title.map_btn.text) if fresh.title.map_btn != null else ""
	if vs_label.contains("Vitriol Sump") or vs_label.contains("Signal Court"):
		errors.append("VS Map must stay on the VS cycle, not the Stage map got %s" % vs_label)
	if fresh.vs_map_id == "police" or fresh.vs_map_id == "hazardous":
		errors.append("vs_map_id must not inherit the Stage map")
	var score_before_reset: int = int(_Stage.load_or_empty().get("score", -1))
	_sanitize_input(fresh)
	await _ui_frames(fresh)
	await _click_control_only(fresh, fresh.title.reset_stage_btn)
	await _ui_frames(fresh)
	var armed: bool = (
		fresh.title.reset_armed
		and fresh.title.confirm_reset_btn != null
		and fresh.title.confirm_reset_btn.visible
		and str(fresh.title.confirm_reset_btn.text) == "Confirm Reset"
		and str(fresh.title.reset_stage_btn.text) == "Reset Stage"
		and int(_Stage.load_or_empty().get("score", -2)) == score_before_reset
	)
	if not armed:
		errors.append("RESET first click must arm Confirm Reset without wiping")
	await _click_control_only(fresh, fresh.title.confirm_reset_btn)
	await _ui_frames(fresh)
	var wiped: Dictionary = _Stage.load_or_empty()
	var reset_ok: bool = (
		armed
		and int(wiped.get("current_index", -1)) == 0
		and int(wiped.get("score", -1)) == 0
		and _array(wiped.get("awarded", [])).is_empty()
		and str(fresh.title.reset_stage_btn.text) == "Reset Stage"
		and (fresh.title.confirm_reset_btn == null or not fresh.title.confirm_reset_btn.visible)
	)
	still_paths["reset"] = await _capture_still(fresh, "stage_reset")
	_append(errors, await _title_start_stage(fresh))
	session = fresh.session
	var fresh_start: bool = session != null and session.map_id == "rooftops" and session.stage_index == 0
	if not reset_ok or not fresh_start:
		errors.append("RESET did not wipe and restart rooftops")
	_note("reset_rooftops", session, {"score": int(wiped.get("score", -1))})
	fresh.restart_to_title()
	await _ui_frames(fresh)
	if fresh.title != null:
		fresh.title.refresh_stage_caption()
	var title_after_ok: bool = (
		fresh.title != null
		and fresh.title.visible
		and fresh.session == null
		and fresh.flow_phase == "title"
		and str(fresh.title.stage_btn.text) == "Stage"
		and not str(fresh.title.map_btn.text).contains("Vitriol Sump")
		and not str(fresh.title.map_btn.text).contains("Signal Court")
	)
	if not title_after_ok:
		errors.append("title_after must be a title screen, not a fight")
	still_paths["title_after"] = await _capture_still(fresh, "stage_title_after")
	outcome_reset = {
		"verdict": "pass" if reset_ok and fresh_start and title_after_ok else "fail",
		"score": int(wiped.get("score", -1)),
		"index": int(wiped.get("current_index", -1)),
		"map_id": session.map_id if session != null else "",
		"title_after_phase": fresh.flow_phase,
		"source": "two distinct clicks: Reset Stage then Confirm Reset; VS Map stays VS cycle",
	}
	outcome_live = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"title_visible_after": fresh.title != null and fresh.title.visible,
		"timeline_len": timeline.size(),
		"events_len": events_all.size(),
		"source": "window/menu Stage/Reset/Rematch clicks + live catalog apply_frames melee",
	}
	return errors


static func _win_on_catalog(app: App, index: int, fight_map: String, next_map: String) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var session: GameSession = app.session
	if session == null or session.map_id != fight_map or session.stage_index != index:
		errors.append("WIN start map=%s idx=%d want %s/%d" % [
			str(session.map_id if session != null else ""),
			session.stage_index if session != null else -1,
			fight_map,
			index,
		])
		return errors
	if session.map_id == "fx_melee_close":
		errors.append("WIN must not use Close Clinch")
		return errors
	_note("win_start", session, {"index": index})
	var hash_before: String = str(_Stage.load_or_empty().get("reward_hash", ""))
	var fight: Dictionary = await _catalog_resolve(app, "win")
	await _wait_advance(app)
	session = app.session
	var progress: Dictionary = _Stage.load_or_empty()
	var dest: String = session.map_id if session != null else ""
	var dest_idx: int = session.stage_index if session != null else -1
	var last: bool = index >= _Stage.stage_count() - 1
	var dest_ok: bool = dest == next_map
	if last:
		dest_ok = dest == fight_map and bool(progress.get("cleared", false))
	var ok: bool = (
		bool(fight.get("ok", false))
		and str(fight.get("map_id", "")) == fight_map
		and str(fight.get("death_cause", "")) == "damage"
		and dest_ok
		and str(progress.get("reward_hash", "")) != hash_before
	)
	if not ok:
		errors.append(
			"WIN %s dest=%s idx=%d cause=%s fight=%s"
			% [fight_map, dest, dest_idx, str(fight.get("death_cause", "")), str(fight)]
		)
	var row: Dictionary = {
		"index": index,
		"fight_map": fight_map,
		"next_map": dest,
		"death_cause": str(fight.get("death_cause", "")),
		"end_reason": str(fight.get("end_reason", "")),
		"bot_deaths": fight.get("bot_deaths", []),
		"reward_hash": str(progress.get("reward_hash", "")),
		"score": int(progress.get("score", -1)),
		"tick": int(fight.get("tick", -1)),
	}
	win_rows.append(row)
	_note("win", session, row)
	return errors


static func _catalog_resolve(app: App, want: String) -> Dictionary:
	var session: GameSession = app.session
	var out: Dictionary = {
		"ok": false,
		"map_id": session.map_id if session != null else "",
		"outcome": session.outcome if session != null else "",
	}
	if session == null:
		return out
	var fight_map: String = session.map_id
	if fight_map == "fx_melee_close":
		out["error"] = "close_clinch"
		return out
	_sanitize_input(app)
	await _typed_idle(app, 4)
	police_cross = 0
	var p1_tagged_bot: bool = false
	var cycle: int = 0
	var stuck: int = 0
	var last_x: float = 0.0
	var hunt_limit: int = 2400
	if fight_map == "police" or fight_map == "hazardous":
		hunt_limit = 3600
	var p1: Fighter = session.player1()
	if p1 != null:
		last_x = p1.global_position.x
	while cycle < hunt_limit and session != null and session.outcome == "play":
		if session.map_id != fight_map:
			out["error"] = "map_swapped"
			break
		p1 = session.player1()
		var foe: Fighter = _first_living_foe(session)
		if p1 == null:
			break
		if absf(p1.global_position.x - last_x) < 1.0:
			stuck += 1
		else:
			stuck = 0
			last_x = p1.global_position.x
		if want == "lose":
			if foe != null and _first_bot_hp(session) < 99.5:
				p1_tagged_bot = true
			if p1_tagged_bot:
				await _tick_driven(app, _hold_cmd(session, p1, foe), _bot_attack_cmd(session, p1))
			else:
				await _tick_driven(app, _intent_cmd(session, p1, foe, true, stuck), {})
		else:
			var extra_bots: Dictionary = {}
			if fight_map == "police":
				extra_bots = _police_bot_cmds(session)
			elif fight_map == "hazardous":
				extra_bots = _hazardous_bot_cmds(session, p1)
			await _tick_driven(app, _intent_cmd(session, p1, foe, true, stuck), extra_bots)
		if cycle % 90 == 0:
			print(
				"HH_VF_STAGE HUNT want=%s map=%s tick=%d p1=(%.1f,%.1f) foe=%s foe_hp=%.1f p1_hp=%.1f stuck=%d live_bots=%d cross=%d bots=%s"
				% [
					want,
					session.map_id,
					session.clock.tick,
					p1.global_position.x,
					p1.global_position.y,
					str(foe.global_position if foe != null else Vector2.ZERO),
					_first_bot_hp(session),
					p1.health,
					stuck,
					_count_living_bots(session),
					police_cross,
					_bot_pos_debug(session),
				]
			)
		cycle += 1
	session = app.session
	p1 = session.player1() if session != null else null
	var death_cause: String = ""
	var bot_deaths: Array = []
	var end_reason: String = ""
	var end_tick: int = -1
	var end_outcome: String = ""
	if session != null:
		end_outcome = session.outcome
		end_tick = session.clock.tick if session.clock != null else -1
		if session.match_rules != null:
			end_reason = session.match_rules.end_reason
		var i: int = 0
		while i < session.fighters.size():
			var f: Fighter = session.fighters[i]
			i += 1
			if f == null or not f.dead:
				continue
			if f == p1:
				death_cause = f.death_cause
			elif f.is_bot:
				bot_deaths.append({"slot": f.slot, "death_cause": f.death_cause, "hp": f.health})
				if death_cause == "":
					death_cause = f.death_cause
		_harvest(session)
	await _ui_frames(app)
	var want_outcome: String = "win" if want == "win" else "lose"
	var bots_damage: bool = true
	var d: int = 0
	while d < bot_deaths.size():
		var row: Dictionary = bot_deaths[d] as Dictionary
		d += 1
		if str(row.get("death_cause", "")) != "damage":
			bots_damage = false
	var cause_ok: bool = death_cause == "damage"
	if want == "win":
		cause_ok = death_cause == "damage" and bots_damage
	out["ok"] = end_outcome == want_outcome and cause_ok and fight_map != "fx_melee_close"
	out["outcome"] = end_outcome
	out["map_id"] = fight_map
	out["death_cause"] = death_cause
	out["end_reason"] = end_reason
	out["bot_deaths"] = bot_deaths
	out["p1_tagged_bot"] = p1_tagged_bot
	out["tick"] = end_tick
	out["cycles"] = cycle
	print(
		"HH_VF_STAGE RESOLVE want=%s ok=%s map=%s outcome=%s cause=%s tick=%d"
		% [want, str(out["ok"]), str(out["map_id"]), str(out["outcome"]), death_cause, int(out["tick"])]
	)
	return out


static func _intent_cmd(session: GameSession, actor: Fighter, target: Fighter, may_melee: bool, stuck: int) -> Dictionary:
	var cmd: Dictionary = _idle_cmd()
	if actor == null or session == null:
		return cmd
	if session.map_id == "rooftops":
		return _rooftops_intent(session, actor, target, may_melee)
	if session.map_id == "police":
		return _police_intent(session, actor, target, may_melee, stuck)
	if session.map_id == "hazardous":
		return _hazardous_intent(session, actor, target, may_melee, stuck)
	return _generic_intent(session, actor, target, may_melee, stuck)


static func _rooftops_intent(session: GameSession, actor: Fighter, target: Fighter, may_melee: bool) -> Dictionary:
	var cmd: Dictionary = _idle_cmd()
	var x: float = actor.global_position.x
	var y: float = actor.global_position.y
	if target != null:
		var dx: float = target.global_position.x - x
		var dy: float = target.global_position.y - y
		if absf(dx) <= 20.0 and absf(dy) <= 18.0:
			cmd["x"] = 1.0 if dx >= 0.0 else -1.0
			if may_melee:
				cmd["melee"] = (session.clock.tick % 12) == 0
			return cmd
	if y > 108.0 and x < 190.0:
		if x < 155.0:
			cmd["x"] = 1.0
			return cmd
		cmd["jump"] = true
		cmd["jump_pressed"] = (session.clock.tick % 8) == 0
		return cmd
	if y <= 110.0 and x < 200.0:
		cmd["x"] = 1.0
		cmd["jump_pressed"] = (session.clock.tick % 6) == 0
		cmd["jump"] = false
		return cmd
	if y <= 110.0 and x < 430.0:
		cmd["x"] = 1.0
		return cmd
	if target != null and (target.global_position.y - y) > 10.0:
		cmd["crouch"] = true
		cmd["crouch_pressed"] = true
		if absf(target.global_position.x - x) > 12.0:
			cmd["x"] = 1.0 if target.global_position.x >= x else -1.0
		return cmd
	if target != null:
		cmd["x"] = 1.0 if target.global_position.x >= x else -1.0
		if may_melee and absf(target.global_position.x - x) <= 24.0:
			cmd["melee"] = (session.clock.tick % 12) == 0
	return cmd


static func _police_intent(session: GameSession, actor: Fighter, target: Fighter, may_melee: bool, stuck: int) -> Dictionary:
	var cmd: Dictionary = _idle_cmd()
	var x: float = actor.global_position.x
	var y: float = actor.global_position.y
	var wall_x: float = 400.0
	var pit_x: float = 124.0
	var ground_y: float = 168.0
	var court_y: float = 136.0
	if target != null:
		var dx0: float = target.global_position.x - x
		var dy0: float = target.global_position.y - y
		if absf(dx0) <= 20.0 and absf(dy0) <= 18.0:
			cmd["x"] = 1.0 if dx0 >= 0.0 else -1.0
			if may_melee:
				cmd["melee"] = (session.clock.tick % 12) == 0
			return cmd
	var foe_left: bool = target != null and target.global_position.x < wall_x
	if x < pit_x:
		cmd["x"] = 1.0
		if y >= ground_y:
			cmd["jump"] = true
			cmd["jump_pressed"] = (session.clock.tick % 6) == 0
		return cmd
	if foe_left or x >= 420.0:
		if x >= 420.0:
			return _police_hunt_right(session, actor, target, may_melee, stuck)
		return _police_hunt_left(session, actor, target, may_melee, stuck)
	## Tile 25 blocks a ground crossing. Stay on the left court and wait
	## for the right-court bot to come over the ladder.
	if y >= ground_y:
		if x < 180.0:
			cmd["x"] = 1.0
			return cmd
		if x > 270.0:
			cmd["x"] = -1.0
			return cmd
		cmd["jump"] = true
		cmd["jump_pressed"] = (session.clock.tick % 6) == 0
		return cmd
	if x < 190.0:
		cmd["x"] = 1.0
		return cmd
	if x > 270.0:
		cmd["x"] = -1.0
		return cmd
	return cmd


static func _police_hunt_left(session: GameSession, actor: Fighter, target: Fighter, may_melee: bool, stuck: int) -> Dictionary:
	var cmd: Dictionary = _idle_cmd()
	var x: float = actor.global_position.x
	var y: float = actor.global_position.y
	var ground_y: float = 168.0
	var court_y: float = 136.0
	if y >= ground_y:
		if x < 180.0:
			cmd["x"] = 1.0
			return cmd
		if x > 270.0:
			cmd["x"] = -1.0
			return cmd
		cmd["jump"] = true
		cmd["jump_pressed"] = (session.clock.tick % 6) == 0
		return cmd
	if y < court_y:
		cmd["x"] = 1.0
		return cmd
	var dx: float = target.global_position.x - x
	var dy: float = target.global_position.y - y
	if dy < -20.0 and target.global_position.x > 300.0:
		cmd["x"] = 1.0
		cmd["jump"] = true
		cmd["jump_pressed"] = (session.clock.tick % 6) == 0
		if may_melee and absf(dx) <= 28.0 and absf(dy) <= 28.0:
			cmd["melee"] = (session.clock.tick % 8) == 0
		return cmd
	cmd["x"] = 1.0 if dx >= 0.0 else -1.0
	if may_melee and absf(dx) <= 28.0 and absf(dy) <= 28.0:
		cmd["melee"] = (session.clock.tick % 8) == 0
	if stuck > 24 and x > 200.0 and x < 280.0:
		cmd["x"] = -1.0 if (session.clock.tick % 20) < 10 else 1.0
	return cmd


static func _police_hunt_right(session: GameSession, actor: Fighter, target: Fighter, may_melee: bool, stuck: int) -> Dictionary:
	var cmd: Dictionary = _idle_cmd()
	if target == null:
		if stuck > 20:
			cmd["jump"] = true
			cmd["jump_pressed"] = (stuck % 18) == 0
		return cmd
	var dx: float = target.global_position.x - actor.global_position.x
	var dy: float = target.global_position.y - actor.global_position.y
	if absf(dx) <= 20.0 and absf(dy) <= 18.0:
		cmd["x"] = 1.0 if dx >= 0.0 else -1.0
		if may_melee:
			cmd["melee"] = (session.clock.tick % 12) == 0
		return cmd
	cmd["x"] = 1.0 if dx >= 0.0 else -1.0
	if dy < -20.0 and stuck > 10:
		cmd["jump"] = true
		cmd["jump_pressed"] = (session.clock.tick % 8) == 0
	if may_melee and absf(dx) <= 24.0 and absf(dy) <= 24.0:
		cmd["melee"] = (session.clock.tick % 12) == 0
	if stuck > 20:
		cmd["jump"] = true
		cmd["jump_pressed"] = (session.clock.tick % 10) == 0
	return cmd


static func _hazardous_intent(session: GameSession, actor: Fighter, target: Fighter, may_melee: bool, stuck: int) -> Dictionary:
	if target != null and actor.global_position.y < 80.0:
		var drop: float = target.global_position.y - actor.global_position.y
		if drop > 24.0 and _floor_under(session.map_id, actor.global_position + Vector2(0.0, 48.0)):
			var cmd_drop: Dictionary = _idle_cmd()
			cmd_drop["crouch"] = true
			cmd_drop["crouch_pressed"] = true
			return cmd_drop
	var cmd: Dictionary = _generic_intent(session, actor, target, may_melee, stuck)
	if _gap_ahead(session.map_id, actor.global_position, float(cmd.get("x", 1.0)) if absf(float(cmd.get("x", 0.0))) > 0.1 else 1.0):
		cmd["jump"] = true
		cmd["jump_pressed"] = (session.clock.tick % 8) == 0
	return cmd


static func _generic_intent(session: GameSession, actor: Fighter, target: Fighter, may_melee: bool, stuck: int) -> Dictionary:
	var cmd: Dictionary = _idle_cmd()
	if target == null:
		if stuck > 20:
			cmd["jump"] = true
			cmd["jump_pressed"] = (stuck % 18) == 0
		return cmd
	var dx: float = target.global_position.x - actor.global_position.x
	var dy: float = target.global_position.y - actor.global_position.y
	var dir: float = 1.0 if dx >= 0.0 else -1.0
	var close: bool = absf(dx) <= 20.0 and absf(dy) <= 18.0
	if close and may_melee:
		cmd["x"] = dir
		cmd["melee"] = (session.clock.tick % 12) == 0
		return cmd
	var map_id: String = session.map_id
	var pos: Vector2 = actor.global_position
	var gap: bool = _gap_ahead(map_id, pos, dir)
	if absf(dx) > 22.0:
		if gap and _gap_width(map_id, pos, dir) <= 6:
			cmd["x"] = dir
			cmd["jump"] = true
			cmd["jump_pressed"] = (session.clock.tick % 8) == 0
			return cmd
		if gap and _near_ladder(map_id, pos) and not _same_level_floor(map_id, pos, dir):
			cmd["jump"] = true
			cmd["jump_pressed"] = true
			return cmd
		cmd["x"] = dir
		if stuck > 24:
			cmd["jump"] = true
			cmd["jump_pressed"] = (session.clock.tick % 14) == 0
		return cmd
	if dy < -16.0:
		cmd["jump"] = true
		cmd["jump_pressed"] = (session.clock.tick % 10) == 0
		if absf(dx) > 8.0:
			cmd["x"] = dir
		return cmd
	if dy > 16.0 and _floor_under(map_id, pos + Vector2(0.0, 40.0)):
		cmd["crouch"] = true
		cmd["crouch_pressed"] = true
		return cmd
	cmd["x"] = dir
	if may_melee and absf(dx) <= 24.0:
		cmd["melee"] = (session.clock.tick % 12) == 0
	return cmd


static func _hold_cmd(session: GameSession, actor: Fighter, target: Fighter) -> Dictionary:
	var cmd: Dictionary = _idle_cmd()
	if actor == null or target == null:
		return cmd
	var dx: float = target.global_position.x - actor.global_position.x
	if absf(dx) > 6.0:
		cmd["x"] = 1.0 if dx >= 0.0 else -1.0
	return cmd


static func _hazardous_bot_cmds(session: GameSession, p1: Fighter) -> Dictionary:
	var out: Dictionary = {}
	if session == null or p1 == null:
		return out
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or not f.is_bot or f.dead:
			continue
		if f.global_position.x <= p1.global_position.x + 40.0:
			continue
		var cmd: Dictionary = _idle_cmd()
		cmd["x"] = -1.0
		if _gap_ahead(session.map_id, f.global_position, -1.0):
			cmd["jump"] = true
			cmd["jump_pressed"] = (session.clock.tick % 8) == 0
		out[f.slot] = cmd
	return out


static func _police_bot_cmds(session: GameSession) -> Dictionary:
	var out: Dictionary = {}
	if session == null:
		return out
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or not f.is_bot or f.dead:
			continue
		if f.global_position.x < 360.0 and f.global_position.y > 130.0:
			continue
		out[f.slot] = _police_bot_come_left(session, f)
	return out


static func _police_bot_come_left(session: GameSession, bot: Fighter) -> Dictionary:
	var cmd: Dictionary = _idle_cmd()
	var x: float = bot.global_position.x
	var y: float = bot.global_position.y
	var ladder50: float = 808.0
	var ladder26: float = 424.0
	var pillar_x: float = 528.0
	if x >= 816.0:
		cmd["x"] = -1.0 if x > ladder50 else 1.0
		if absf(x - ladder50) <= 28.0:
			cmd["jump"] = true
			cmd["jump_pressed"] = true
		return cmd
	if y <= 130.0:
		cmd["x"] = -1.0
		if x <= 460.0:
			cmd["jump"] = true
			cmd["jump_pressed"] = (session.clock.tick % 8) == 0
		return cmd
	if x > pillar_x:
		if absf(x - ladder50) <= 22.0:
			cmd["jump"] = true
			cmd["jump_pressed"] = true
			return cmd
		cmd["x"] = -1.0 if x > ladder50 else 1.0
		if absf(x - ladder50) <= 36.0:
			cmd["jump"] = true
			cmd["jump_pressed"] = (session.clock.tick % 6) == 0
		return cmd
	if absf(x - ladder26) <= 22.0:
		cmd["jump"] = true
		cmd["jump_pressed"] = true
		if y <= 112.0:
			cmd["x"] = -1.0
		return cmd
	cmd["x"] = -1.0 if x > ladder26 else 1.0
	if absf(x - ladder26) <= 36.0:
		cmd["jump"] = true
		cmd["jump_pressed"] = (session.clock.tick % 6) == 0
	return cmd


static func _bot_attack_cmd(session: GameSession, p1: Fighter) -> Dictionary:
	var foe: Fighter = _first_living_foe(session)
	if foe == null or p1 == null:
		return {}
	var cmd: Dictionary = _idle_cmd()
	var dx: float = p1.global_position.x - foe.global_position.x
	cmd["x"] = 1.0 if dx >= 0.0 else -1.0
	cmd["melee"] = (session.clock.tick % 10) == 0
	return {foe.slot: cmd}


static func _idle_cmd() -> Dictionary:
	return {
		"x": 0.0,
		"jump": false,
		"jump_pressed": false,
		"crouch": false,
		"crouch_pressed": false,
		"melee": false,
		"roll": false,
		"dive": false,
		"kick": false,
		"fire_held": false,
		"fire_released": false,
	}


static func _tick_driven(app: App, p1_cmd: Dictionary, bot_cmds: Dictionary) -> void:
	if app == null or app.session == null:
		return
	var session: GameSession = app.session
	_sanitize_input(app)
	_inject_p1_cmd(app, p1_cmd)
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and f.is_human and f.slot == 0:
			frames.append(InputActions.frame_from_cmd(p1_cmd, session.clock.tick, 0))
		elif f != null and bot_cmds.has(f.slot):
			var raw: Dictionary = (bot_cmds[f.slot] as Dictionary).duplicate(true)
			frames.append(InputActions.frame_from_cmd(raw, session.clock.tick, f.slot))
		else:
			frames.append(InputFrame.from_dict(InputActions.empty_frame(session.clock.tick, i)))
		i += 1
	used_apply_frames_attempted += 1
	if session.apply_frames(frames):
		used_apply_frames_succeeded += 1
		used_apply_frames += 1
	_release_all_p1(app)


static func _inject_p1_cmd(app: App, cmd: Dictionary) -> void:
	if app == null or app.get_viewport() == null:
		return
	var vp: Viewport = app.get_viewport()
	var x: float = float(cmd.get("x", 0.0))
	if x > 0.35:
		InputInjector.inject_key(KEY_RIGHT, true, vp)
		used_parse_input_event += 1
	elif x < -0.35:
		InputInjector.inject_key(KEY_LEFT, true, vp)
		used_parse_input_event += 1
	if bool(cmd.get("jump", false)) or bool(cmd.get("jump_pressed", false)):
		InputInjector.inject_key(KEY_UP, true, vp)
		used_parse_input_event += 1
	if bool(cmd.get("crouch", false)):
		InputInjector.inject_key(KEY_DOWN, true, vp)
		used_parse_input_event += 1
	if bool(cmd.get("melee", false)):
		InputInjector.inject_key(KEY_N, true, vp)
		used_parse_input_event += 1


static func _release_all_p1(app: App) -> void:
	if app == null or app.get_viewport() == null:
		InputActions.reset_edges()
		return
	var vp: Viewport = app.get_viewport()
	var keys: Array = [KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN, KEY_N]
	var i: int = 0
	while i < keys.size():
		InputInjector.inject_key(keys[i] as Key, false, vp)
		i += 1
	InputActions.reset_edges()


static func _cell_ch(map_id: String, wx: float, wy: float) -> String:
	var rows: PackedStringArray = Maps.grid(map_id)
	var cx: int = int(floor(wx / float(Maps.TILE)))
	var cy: int = int(floor(wy / float(Maps.TILE)))
	if cy < 0 or cy >= rows.size():
		return "."
	var row: String = String(rows[cy])
	if cx < 0 or cx >= row.length():
		return "."
	return row.substr(cx, 1)


static func _support(map_id: String, wx: float, wy: float) -> bool:
	var ch: String = _cell_ch(map_id, wx, wy)
	return Maps.is_solid(ch) or Maps.is_platform(ch) or ch == "c" or ch == "b"


static func _floor_under(map_id: String, pos: Vector2) -> bool:
	return (
		_support(map_id, pos.x, pos.y + 4.0)
		or _support(map_id, pos.x, pos.y + 12.0)
		or _support(map_id, pos.x, pos.y + 20.0)
		or _support(map_id, pos.x, pos.y + 28.0)
	)


static func _same_level_floor(map_id: String, pos: Vector2, dir: float) -> bool:
	var ax: float = pos.x + dir * 14.0
	return _support(map_id, ax, pos.y + 4.0) or _support(map_id, ax, pos.y + 12.0)


static func _gap_ahead(map_id: String, pos: Vector2, dir: float) -> bool:
	return not _same_level_floor(map_id, pos, dir) and not _floor_under(map_id, pos + Vector2(dir * 16.0, 0.0))


static func _gap_width(map_id: String, pos: Vector2, dir: float) -> int:
	var n: int = 0
	while n < 12:
		if _floor_under(map_id, pos + Vector2(dir * float((n + 1) * Maps.TILE), 0.0)):
			return n
		n += 1
	return n


static func _near_ladder(map_id: String, pos: Vector2) -> bool:
	var ox: PackedInt32Array = PackedInt32Array([-16, -8, 0, 8, 16])
	var oy: PackedInt32Array = PackedInt32Array([-24, -8, 0, 8, 24])
	var i: int = 0
	while i < ox.size():
		var j: int = 0
		while j < oy.size():
			if Maps.is_ladder(_cell_ch(map_id, pos.x + float(ox[i]), pos.y + float(oy[j]))):
				return true
			j += 1
		i += 1
	return false


static func _ladder_dir(map_id: String, pos: Vector2, prefer: float) -> float:
	var best: float = prefer
	var best_d: float = 9999.0
	var x: int = -8
	while x <= 8:
		var wx: float = pos.x + float(x * Maps.TILE)
		if Maps.is_ladder(_cell_ch(map_id, wx, pos.y)) or Maps.is_ladder(_cell_ch(map_id, wx, pos.y + 16.0)):
			var d: float = absf(wx - pos.x)
			if d < best_d:
				best_d = d
				best = 1.0 if wx >= pos.x else -1.0
		x += 1
	return best


static func _title_start_stage(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.restart_to_title()
	await _ui_frames(app)
	if app.title == null or app.title.stage_btn == null:
		errors.append("title missing Stage")
		return errors
	if app.title != null:
		app.title.refresh_stage_caption()
	await _activate_button(app, app.title.stage_btn, "fight")
	await SimReplay.sync_physics(app)
	if app.session == null or app.session.mode != "stage":
		errors.append("title Stage missed session")
	return errors


static func _wait_advance(app: App) -> void:
	var n: int = 0
	while n < 10:
		await _ui_frames(app)
		if app.get_tree() != null:
			await app.get_tree().process_frame
		n += 1
	await SimReplay.sync_physics(app)


static func _first_living_foe(session: GameSession) -> Fighter:
	if session == null:
		return null
	var p1: Fighter = session.player1()
	var best: Fighter = null
	var best_d: float = 99999.0
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or f == p1 or f.dead:
			continue
		var d: float = 99999.0
		if p1 != null:
			d = p1.global_position.distance_to(f.global_position)
		if d < best_d:
			best_d = d
			best = f
	return best


static func _first_bot_hp(session: GameSession) -> float:
	var foe: Fighter = _first_living_foe(session)
	if foe != null:
		return foe.health
	if session == null:
		return -1.0
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f != null and f.is_bot:
			return f.health
	return -1.0


static func _count_is_bot(session: GameSession) -> int:
	if session == null:
		return 0
	var n: int = 0
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f != null and f.is_bot:
			n += 1
	return n


static func _count_living_bots(session: GameSession) -> int:
	if session == null:
		return 0
	var n: int = 0
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f != null and f.is_bot and not f.dead:
			n += 1
	return n


static func _bot_pos_debug(session: GameSession) -> String:
	if session == null:
		return ""
	var parts: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == null or not f.is_bot:
			continue
		parts.append(
			"%d:%s(%.0f,%.0f,hp=%.0f)"
			% [f.slot, "dead" if f.dead else "live", f.global_position.x, f.global_position.y, f.health]
		)
	return ",".join(parts)


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"SCHEMA", "LOAD", "ADVANCE", "LOSS", "HASH", "CONTINUE", "RESET", "LIVE"
	])
	var rows: Array = [
		outcome_schema, outcome_load, outcome_advance, outcome_loss,
		outcome_hash, outcome_continue, outcome_reset, outcome_live
	]
	var i: int = 0
	while i < labels.size():
		var row: Dictionary = rows[i] as Dictionary
		if str(row.get("verdict", "")) != "pass":
			errors.append("%s outcome is %s" % [String(labels[i]), str(row.get("verdict", "unproven"))])
		i += 1
	if used_force_kill != 0:
		errors.append("official stage used force_kill")
	if used_teleport != 0:
		errors.append("official stage used teleport")
	if used_step_fixed != 0:
		errors.append("official stage used step_fixed")
	if used_apply_eval != 0:
		errors.append("official stage used apply_eval")
	if timeline.is_empty():
		errors.append("official stage need a full timeline")
	if events_all.is_empty():
		errors.append("official stage need events.jsonl rows")
	if str(outcome_loss.get("death_cause", "")) == "pit":
		errors.append("official E2E loss cannot be pit")
	return errors


static func _click_control_only(app: App, btn: Button) -> void:
	if app == null or btn == null:
		return
	_sanitize_input(app)
	await _ui_frames(app)
	await _click_control_async(app, btn)
	await _ui_frames(app)


static func _activate_button(app: App, btn: Button, kind: String) -> void:
	if app == null or btn == null:
		return
	var before: String = _probe(app, kind)
	used_parse_input_event += 1
	btn.grab_focus()
	await _ui_frames(app)
	_click_control(app, btn)
	await _ui_frames(app)
	if _probe(app, kind) != before:
		return
	_push_key(app, KEY_ENTER)
	await _ui_frames(app)
	if _probe(app, kind) != before:
		return
	_push_action(app, "ui_accept")
	await _ui_frames(app)


static func _probe(app: App, kind: String) -> String:
	if kind == "fight":
		return "1" if app.session != null else "0"
	if kind == "reset":
		return str(int(_Stage.load_or_empty().get("score", 0)))
	if kind == "rematch":
		if app.session != null and app.session.match_rules != null:
			return "%d:%s" % [app.session.match_rules.round_id, app.session.get_instance_id()]
		return "0"
	return ""


static func _sanitize_input(app: App) -> void:
	if app == null or app.get_viewport() == null:
		InputActions.reset_edges()
		return
	var vp: Viewport = app.get_viewport()
	InputInjector.release_known(vp)
	Input.flush_buffered_events()
	InputInjector.release_known(vp)
	InputActions.reset_edges()


static func _typed_idle(app: App, ticks: int) -> void:
	var n: int = 0
	while n < ticks and app != null and app.session != null and app.session.outcome == "play":
		_tick_driven(app, _idle_cmd(), {})
		n += 1


static func _ui_frames(app: App) -> void:
	if app == null or app.get_tree() == null:
		return
	var tree: SceneTree = app.get_tree()
	await tree.process_frame
	await tree.process_frame


static func _mouse_at(ctrl: Control, pressed: bool) -> InputEventMouseButton:
	var pos: Vector2 = ctrl.get_global_rect().get_center()
	var ev: InputEventMouseButton = InputEventMouseButton.new()
	ev.button_index = MOUSE_BUTTON_LEFT
	ev.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
	ev.pressed = pressed
	ev.position = pos
	ev.global_position = pos
	return ev


static func _inject_mouse(app: App, ev: InputEventMouseButton) -> void:
	if app == null or app.get_viewport() == null:
		return
	Input.parse_input_event(ev)
	Input.flush_buffered_events()
	app.get_viewport().push_input(ev, true)
	used_parse_input_event += 1


static func _click_control(app: App, ctrl: Control) -> void:
	if app == null or ctrl == null or app.get_viewport() == null:
		return
	_inject_mouse(app, _mouse_at(ctrl, true))
	_inject_mouse(app, _mouse_at(ctrl, false))


static func _click_control_async(app: App, ctrl: Control) -> void:
	if app == null or ctrl == null or app.get_viewport() == null:
		return
	_inject_mouse(app, _mouse_at(ctrl, true))
	await _ui_frames(app)
	_inject_mouse(app, _mouse_at(ctrl, false))


static func _push_key(app: App, key: Key) -> void:
	if app == null:
		return
	var vp: Viewport = app.get_viewport()
	InputInjector.inject_key(key, true, vp)
	used_parse_input_event += 1
	InputInjector.inject_key(key, false, vp)
	used_parse_input_event += 1


static func _push_action(app: App, action: String) -> void:
	if app == null or app.get_viewport() == null:
		return
	var ev: InputEventAction = InputEventAction.new()
	ev.action = action
	ev.pressed = true
	app.get_viewport().push_input(ev)
	used_parse_input_event += 1
	var rel: InputEventAction = InputEventAction.new()
	rel.action = action
	rel.pressed = false
	app.get_viewport().push_input(rel)
	used_parse_input_event += 1


static func _capture_still(app: App, stem: String) -> String:
	var ev: String = OS.get_environment("HH_VF_EVIDENCE_DIR")
	if ev == "":
		ev = ProjectSettings.globalize_path("res://.evidence/%s" % RUN_ID)
	DirAccess.make_dir_recursive_absolute(ev.path_join("screens"))
	if DisplayServer.get_name() == "headless":
		return ""
	if app == null or app.get_viewport() == null:
		return ""
	if app.get_tree() != null:
		await app.get_tree().process_frame
	await RenderingServer.frame_post_draw
	var vis: Rect2 = app.get_viewport().get_visible_rect()
	var tex: ViewportTexture = app.get_viewport().get_texture()
	if tex == null:
		return ""
	var img: Image = tex.get_image()
	if img == null:
		return ""
	var shot: String = ev.path_join("screens").path_join("%s_%dx%d.png" % [stem, int(vis.size.x), int(vis.size.y)])
	var err: Error = img.save_png(shot)
	print("HH_VF_STAGE SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
	return shot


static func _note(at: String, session: GameSession, extra: Dictionary) -> void:
	var row: Dictionary = extra.duplicate(true)
	row["at"] = at
	if session != null:
		row["map_id"] = session.map_id
		row["stage_index"] = session.stage_index
		row["tick"] = session.clock.tick if session.clock != null else -1
		row["outcome"] = session.outcome
		row["bots"] = session.live_bot_count()
		if session.match_rules != null:
			row["end_reason"] = session.match_rules.end_reason
	row["reward_hash"] = str(_Stage.load_or_empty().get("reward_hash", ""))
	timeline.append(row)


static func _harvest(session: GameSession) -> void:
	if session == null or session.ledger == null:
		return
	var rows: Array = session.ledger.to_array()
	var i: int = 0
	while i < rows.size():
		var raw: Variant = rows[i]
		i += 1
		if not (raw is Dictionary):
			continue
		var copy: Dictionary = (raw as Dictionary).duplicate(true)
		copy["map_id"] = session.map_id
		copy["stage_index"] = session.stage_index
		events_all.append(copy)


static func _array(value: Variant) -> Array:
	if value is Array:
		return value as Array
	return []


static func _append(into: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		into.append(String(extra[i]))
		i += 1
