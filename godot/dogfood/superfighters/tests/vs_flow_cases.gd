class_name VsFlowCases
extends RefCounted

## VF6-WP2 production VS 1P / local VS 2P flow.
## Official proof is title/lobby/result clicks plus parse_input_event.
## No teleport. No force_kill. Bots stay smoke. VS does not start Survival; Title Survival is shipped separately.

const _VsFlow: GDScript = preload("res://src/sim/vs_flow.gd")
const RUN_ID := "VF6WP2-20260901-ASIA-SAIGON-03"

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var used_force_kill: int = 0
static var used_teleport: int = 0
static var outcome_schema: Dictionary = {}
static var outcome_first: Dictionary = {}
static var outcome_ready: Dictionary = {}
static var outcome_leak: Dictionary = {}
static var outcome_play: Dictionary = {}
static var outcome_rematch: Dictionary = {}
static var outcome_overlay: Dictionary = {}
static var outcome_feedback: Dictionary = {}
static var outcome_live: Dictionary = {}
static var still_paths: Dictionary = {}
static var timeline: Array = []
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var events_all: Array = []


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	used_force_kill = 0
	used_teleport = 0
	outcome_schema = {"verdict": "unproven"}
	outcome_first = {"verdict": "unproven"}
	outcome_ready = {"verdict": "unproven"}
	outcome_leak = {"verdict": "unproven"}
	outcome_play = {"verdict": "unproven"}
	outcome_rematch = {"verdict": "unproven"}
	outcome_overlay = {"verdict": "unproven"}
	outcome_feedback = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	still_paths = {}
	timeline = []
	snapshot_start = {}
	snapshot_end = {}
	events_all = []
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_contract())
	print("HH_VF_VS2 STEP=first_run")
	_append(errors, await first_run_paths(app))
	print("HH_VF_VS2 STEP=ready_remap")
	_append(errors, await ready_and_remap(app))
	print("HH_VF_VS2 STEP=play_resolve")
	_append(errors, await two_player_resolve(app))
	print("HH_VF_VS2 STEP=rematch")
	_append(errors, await rematch_and_overlay(app))
	print("HH_VF_VS2 STEP=leak")
	_append(errors, await leak_and_feedback(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_contract() -> PackedStringArray:
	var errors: PackedStringArray = _VsFlow.validate()
	if bool(_VsFlow.payload().get("survival_shipped", false)):
		errors.append("vs_flow must not start Survival as a VS path")
	if not bool(_VsFlow.payload().get("title_survival_shipped", false)):
		errors.append("vs_flow catalog must acknowledge Title Survival is shipped")
	outcome_schema = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"source": "data/sim/vs_flow.json",
	}
	return errors


static func first_run_paths(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.restart_to_title()
	await _ui_frames(app)
	still_paths["title"] = await _capture_still(app, "vs_flow_title")
	var vs1: Dictionary = await _first_run(app, "vs1", app.title.vs_one_btn)
	var vs2: Dictionary = await _first_run(app, "vs2", app.title.vs_two_btn)
	var ok: bool = (
		bool(vs1.get("ok", false))
		and bool(vs2.get("ok", false))
		and int(vs1.get("actions", 99)) <= 3
		and int(vs2.get("actions", 99)) <= 3
		and float(vs1.get("seconds", 99.0)) <= 30.0
		and float(vs2.get("seconds", 99.0)) <= 30.0
	)
	if not ok:
		errors.append("FIRST_RUN vs1=%s vs2=%s" % [JSON.stringify(vs1), JSON.stringify(vs2)])
	outcome_first = {
		"verdict": "pass" if ok else "fail",
		"vs1_actions": int(vs1.get("actions", 99)),
		"vs1_seconds": float(vs1.get("seconds", 99.0)),
		"vs2_actions": int(vs2.get("actions", 99)),
		"vs2_seconds": float(vs2.get("seconds", 99.0)),
		"path": "title → VS 1P/2P → Start",
		"source": "viewport button clicks; no editor; no teleport",
	}
	outcome_ready = {
		"verdict": "pass" if ok and bool(vs1.get("ready", false)) and bool(vs2.get("ready", false)) else "fail",
		"source": "lobby ready auto-seat + Start",
	}
	return errors


static func _first_run(app: App, want_mode: String, mode_btn: Button) -> Dictionary:
	app.restart_to_title()
	await _ui_frames(app)
	if app.title == null or mode_btn == null:
		return {"ok": false, "reason": "missing title"}
	var t0: float = Time.get_ticks_msec()
	var actions: int = 0
	await _activate_button(app, mode_btn, "lobby")
	actions += 1
	_note("first_run_%s_mode" % want_mode, actions, Time.get_ticks_msec() - t0)
	if app.lobby == null or not app.lobby.visible or not app.lobby.can_start():
		return {"ok": false, "reason": "lobby not ready", "actions": actions}
	still_paths["lobby"] = await _capture_still(app, "vs_flow_lobby")
	await _activate_button(app, app.lobby.start_btn, "fight")
	actions += 1
	await SimReplay.sync_physics(app)
	var sec: float = (Time.get_ticks_msec() - t0) / 1000.0
	_note("first_run_%s_start" % want_mode, actions, Time.get_ticks_msec() - t0)
	var ok: bool = (
		app.session != null
		and app.session.mode == want_mode
		and app.session.outcome == "play"
		and not app.title.visible
		and (app.lobby == null or not app.lobby.visible)
		and not app.overlay_leaking()
	)
	if ok and snapshot_start.is_empty():
		snapshot_start = app.session.snapshot()
	return {
		"ok": ok,
		"actions": actions,
		"seconds": sec,
		"ready": app.lobby == null or not app.lobby.visible,
		"mode": want_mode,
	}


static func ready_and_remap(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.restart_to_title()
	await _ui_frames(app)
	await _activate_button(app, app.title.vs_two_btn, "lobby")
	if app.lobby == null or app.lobby.controls_btn == null:
		errors.append("READY missing lobby Controls")
		return errors
	await _activate_button(app, app.lobby.controls_btn, "remap")
	var remap_up: bool = app.remap_screen != null and app.remap_screen.visible
	if not remap_up:
		errors.append("READY Controls did not open remap")
	if remap_up:
		var back: Button = app.remap_screen.get_node_or_null("Back") as Button
		if back != null:
			await _activate_button(app, back, "remap_back")
	var back_ok: bool = app.lobby != null and app.lobby.visible and (app.remap_screen == null or not app.remap_screen.visible)
	if not back_ok:
		errors.append("READY remap Back did not return to lobby")
	if str(outcome_ready.get("verdict", "")) != "fail":
		outcome_ready["remap"] = remap_up and back_ok
		if not (remap_up and back_ok):
			outcome_ready["verdict"] = "fail"
	return errors


static func leak_and_feedback(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, await _title_start_vs2(app, "police"))
	var session: GameSession = app.session
	if session == null or session.player1() == null or session.player2() == null:
		errors.append("LEAK missing P1/P2")
		outcome_leak = {"verdict": "fail", "source": "missing P1/P2"}
		return errors
	var p1: Fighter = session.player1()
	var p2: Fighter = session.player2()
	var p1_x0: float = p1.global_position.x
	var p2_x0: float = p2.global_position.x
	await _typed_hold_slot(app, KEY_RIGHT, 2)
	var p1_moved: bool = p1.global_position.x > p1_x0 + SimConstants.EPSILON
	var p2_still: bool = absf(p2.global_position.x - p2_x0) <= 1.5
	InputInjector.release_known(app.get_viewport())
	InputActions.reset_edges()
	p1_x0 = p1.global_position.x
	p2_x0 = p2.global_position.x
	await _typed_hold_slot(app, KEY_A, 8)
	var p2_moved: bool = p2.global_position.x < p2_x0 - SimConstants.EPSILON
	var p1_still: bool = absf(p1.global_position.x - p1_x0) <= 1.5
	InputInjector.release_known(app.get_viewport())
	InputActions.reset_edges()
	await _typed_tap(app, KEY_N)
	var p1_melee: bool = p1.attack_phase != "idle" or p1.melee_cd > 0.0
	var p2_idle: bool = p2.attack_phase == "idle"
	var n: int = 0
	while n < 20 and p1.attack_phase != "idle":
		_apply_live_both(session)
		n += 1
	await _typed_tap(app, KEY_1)
	var p2_melee: bool = p2.attack_phase != "idle" or p2.melee_cd > 0.0
	var leak_ok: bool = p1_moved and p2_still and p2_moved and p1_still and p1_melee and p2_idle
	if not leak_ok:
		errors.append(
			"LEAK p1_moved=%s p2_still=%s p2_moved=%s p1_still=%s p1_melee=%s p2_idle=%s"
			% [p1_moved, p2_still, p2_moved, p1_still, p1_melee, p2_idle]
		)
	var feedback_ok: bool = p1_moved
	outcome_leak = {
		"verdict": "pass" if leak_ok else "fail",
		"p1_moved": p1_moved,
		"p2_still_on_p1": p2_still,
		"p2_moved": p2_moved,
		"p1_still_on_p2": p1_still,
		"p1_melee": p1_melee,
		"p2_idle_on_p1": p2_idle,
		"p2_melee": p2_melee,
		"source": "parse_input_event KEY_RIGHT/KEY_A/KEY_N/KEY_1 + live both slots",
	}
	outcome_feedback = {
		"verdict": "pass" if feedback_ok else "fail",
		"frames": 2,
		"p1_moved": p1_moved,
		"source": "P1 KEY_RIGHT acknowledge within 2 sim frames",
	}
	InputInjector.release_known(app.get_viewport())
	InputActions.reset_edges()
	return errors


static func two_player_resolve(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	## Same-map resolve. Title VS 2P is already proven in first_run/leak.
	## Close Clinch keeps both bodies on one floor so the round can end
	## from melee damage. No rooftops restart. No KEY_RIGHT pit walk.
	_sanitize_input(app)
	app.start_fight("vs2", "fx_melee_close", 0)
	await SimReplay.sync_physics(app)
	_sanitize_input(app)
	await _typed_idle(app, 4)
	var session: GameSession = app.session
	if session == null or session.player1() == null or session.player2() == null:
		errors.append("PLAY missing vs2 session")
		outcome_play = {"verdict": "fail"}
		return errors
	if session.map_id != "fx_melee_close":
		errors.append("PLAY map must stay fx_melee_close got=%s" % session.map_id)
	var p1: Fighter = session.player1()
	var p2: Fighter = session.player2()
	var resolve_map: String = session.map_id
	var p1_x0: float = p1.global_position.x
	var p2_x0: float = p2.global_position.x
	var p1_hp0: float = p1.health
	var p2_hp0: float = p2.health
	_sanitize_input(app)
	await _typed_hold_keys(app, [KEY_RIGHT], 3)
	var p1_moved: bool = absf(p1.global_position.x - p1_x0) > SimConstants.EPSILON
	await _typed_hold_keys(app, [KEY_A], 3)
	var p2_moved: bool = absf(p2.global_position.x - p2_x0) > SimConstants.EPSILON
	still_paths["fight"] = await _capture_still(app, "vs_flow_fight")
	_sanitize_input(app)
	await _typed_hold_keys(app, [KEY_1], 8)
	var p2_attacked: bool = p2.melee_cd > 0.0 or p2.attack_phase != "idle"
	await _typed_idle(app, 10)
	await _typed_hold_keys(app, [KEY_N], 8)
	var p1_attacked: bool = p1.melee_cd > 0.0 or p1.attack_phase != "idle"
	await _typed_idle(app, 10)
	var hit_landed: bool = p1.health < p1_hp0 - 0.01 or p2.health < p2_hp0 - 0.01
	var cycle: int = 0
	while cycle < 48 and session != null and session.outcome == "play":
		_sanitize_input(app)
		var face: Key = KEY_RIGHT
		if p2.global_position.x < p1.global_position.x:
			face = KEY_LEFT
		if _horiz_sep(p1, p2) > 24.0:
			await _typed_hold_keys(app, [face], 8)
		InputActions.reset_edges()
		await _typed_hold_keys(app, [face, KEY_N], 8)
		if p1.melee_cd > 0.0 or p1.attack_phase != "idle":
			p1_attacked = true
		await _typed_idle(app, 10)
		if p1.health < p1_hp0 - 0.01 or p2.health < p2_hp0 - 0.01:
			hit_landed = true
		cycle += 1
	await _ui_frames(app)
	p1 = session.player1() if session != null else null
	p2 = session.player2() if session != null else null
	var death_cause: String = ""
	if p1 != null and p1.dead:
		death_cause = p1.death_cause
	elif p2 != null and p2.dead:
		death_cause = p2.death_cause
	var resolved: bool = session != null and session.outcome != "play"
	var died: bool = (p1 != null and p1.dead) or (p2 != null and p2.dead)
	var same_map: bool = session != null and session.map_id == resolve_map and resolve_map == "fx_melee_close"
	var damage_ko: bool = death_cause == "damage" and hit_landed
	var ok: bool = (
		p1_moved
		and p2_moved
		and p1_attacked
		and p2_attacked
		and resolved
		and died
		and same_map
		and damage_ko
		and used_force_kill == 0
		and used_teleport == 0
	)
	print(
		"HH_VF_VS2 PLAY_TRACE map=%s p1_moved=%s p2_moved=%s p1_attacked=%s p2_attacked=%s hit=%s outcome=%s death_cause=%s end_reason=%s hp=%s/%s"
		% [
			resolve_map if session != null else "",
			str(p1_moved),
			str(p2_moved),
			str(p1_attacked),
			str(p2_attacked),
			str(hit_landed),
			str(session.outcome if session != null else ""),
			death_cause,
			str(session.match_rules.end_reason if session != null and session.match_rules != null else ""),
			str(p1.health if p1 != null else -1.0),
			str(p2.health if p2 != null else -1.0),
		]
	)
	if not ok:
		errors.append(
			"PLAY p1_moved=%s p2_moved=%s p1_attacked=%s p2_attacked=%s hit=%s outcome=%s death_cause=%s map=%s"
			% [
				str(p1_moved),
				str(p2_moved),
				str(p1_attacked),
				str(p2_attacked),
				str(hit_landed),
				str(session.outcome if session != null else ""),
				death_cause,
				str(session.map_id if session != null else ""),
			]
		)
	if session != null:
		snapshot_end = session.snapshot()
		if session.ledger != null:
			_append_events(session.ledger.to_array())
	still_paths["result"] = await _capture_still(app, "vs_flow_result")
	outcome_play = {
		"verdict": "pass" if ok else "fail",
		"moved": p1_moved and p2_moved,
		"attacked": p1_attacked and p2_attacked,
		"p1_moved": p1_moved,
		"p2_moved": p2_moved,
		"p1_attacked": p1_attacked,
		"p2_attacked": p2_attacked,
		"hit_landed": hit_landed,
		"died": died,
		"death_cause": death_cause,
		"map_id": session.map_id if session != null else "",
		"outcome": session.outcome if session != null else "",
		"end_reason": session.match_rules.end_reason if session != null and session.match_rules != null else "",
		"used_force_kill": used_force_kill,
		"used_teleport": used_teleport,
		"used_pit_fallback": 0,
		"source": "start_fight fx_melee_close + parse_input_event both slots move+melee; damage last-standing; no rooftops pit fallback",
	}
	return errors


static func rematch_and_overlay(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if app.session == null or app.session.outcome == "play":
		_append(errors, await two_player_resolve(app))
	await _ui_frames(app)
	var overlay: Object = _visible_result(app)
	if overlay == null:
		errors.append("REMATCH missing result overlay")
		outcome_rematch = {"verdict": "fail"}
		return errors
	var rematch_btn: Button = overlay.get("rematch_btn") as Button
	if rematch_btn == null:
		errors.append("REMATCH missing Rematch button")
		outcome_rematch = {"verdict": "fail"}
		return errors
	var before_round: int = 0
	if app.session != null and app.session.match_rules != null:
		before_round = app.session.match_rules.round_id
	var t0: float = Time.get_ticks_msec()
	await _activate_button(app, rematch_btn, "rematch")
	await SimReplay.sync_physics(app)
	var sec: float = (Time.get_ticks_msec() - t0) / 1000.0
	_note("rematch", 1, Time.get_ticks_msec() - t0)
	var session: GameSession = app.session
	var after_round: int = 0
	if session != null and session.match_rules != null:
		after_round = session.match_rules.round_id
	var overlay_hidden: bool = not app.overlay_leaking()
	var title_clean: bool = app.title == null or not app.title.visible or not (
		(app.win_screen != null and app.win_screen.visible)
		or (app.lose_screen != null and app.lose_screen.visible)
		or (app.tie_screen != null and app.tie_screen.visible)
	)
	var ok: bool = (
		session != null
		and session.outcome == "play"
		and after_round != 0
		and after_round != before_round
		and overlay_hidden
		and title_clean
		and (app.lobby == null or not app.lobby.visible)
		and sec <= 5.0
	)
	if not ok:
		errors.append(
			"REMATCH play=%s round %d→%d leak=%s sec=%s"
			% [
				str(session.outcome if session != null else ""),
				before_round,
				after_round,
				str(not overlay_hidden),
				str(sec),
			]
		)
	still_paths["rematch"] = await _capture_still(app, "vs_flow_rematch")
	app.restart_to_title()
	await _ui_frames(app)
	var title_after: bool = app.title != null and app.title.visible and not app.overlay_leaking()
	if not title_after:
		errors.append("OVERLAY title still leaks result after rematch/title")
	if title_after:
		still_paths["title_after"] = await _capture_still(app, "vs_flow_title_after")
	outcome_rematch = {
		"verdict": "pass" if ok else "fail",
		"actions": 1,
		"seconds": sec,
		"round_before": before_round,
		"round_after": after_round,
		"source": "result Rematch click; same mode/map; no lobby hunt",
	}
	outcome_overlay = {
		"verdict": "pass" if overlay_hidden and title_after else "fail",
		"hidden_on_rematch": overlay_hidden,
		"title_clean": title_after,
		"source": "result token + CanvasLayer hide_result",
	}
	outcome_live = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"title_visible_after": title_after,
		"first_run_actions": int(outcome_first.get("vs2_actions", 99)),
		"rematch_actions": 1,
		"source": "window/menu injected keyboard + viewport clicks",
	}
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"SCHEMA", "FIRST", "READY", "LEAK", "PLAY", "REMATCH", "OVERLAY", "FEEDBACK", "LIVE"
	])
	var rows: Array = [
		outcome_schema, outcome_first, outcome_ready, outcome_leak, outcome_play,
		outcome_rematch, outcome_overlay, outcome_feedback, outcome_live
	]
	var i: int = 0
	while i < labels.size():
		var row: Dictionary = rows[i] as Dictionary
		if str(row.get("verdict", "")) != "pass":
			errors.append("%s outcome is %s" % [String(labels[i]), str(row.get("verdict", "unproven"))])
		i += 1
	if used_force_kill != 0:
		errors.append("official vs flow used force_kill")
	if used_teleport != 0:
		errors.append("official vs flow used teleport")
	if used_step_fixed != 0:
		errors.append("official vs flow used step_fixed")
	return errors


static func _title_start_vs2(app: App, map_id: String) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.restart_to_title()
	await _ui_frames(app)
	if app.title == null or app.title.vs_two_btn == null or app.title.map_btn == null:
		errors.append("title missing VS 2P / Map")
		return errors
	var hops: int = 0
	while app.map_id != map_id and hops < 8:
		await _activate_button(app, app.title.map_btn, "map")
		hops += 1
	if app.map_id != map_id:
		errors.append("map cycle missed %s" % map_id)
		return errors
	await _activate_button(app, app.title.vs_two_btn, "lobby")
	if app.lobby == null or app.lobby.start_btn == null:
		errors.append("lobby missing Start")
		return errors
	await _activate_button(app, app.lobby.start_btn, "fight")
	await SimReplay.sync_physics(app)
	if app.session == null or app.session.mode != "vs2":
		errors.append("VS 2P Start missed session")
	return errors


static func _visible_result(app: App) -> Object:
	if app.win_screen != null and app.win_screen.visible:
		return app.win_screen
	if app.lose_screen != null and app.lose_screen.visible:
		return app.lose_screen
	if app.tie_screen != null and app.tie_screen.visible:
		return app.tie_screen
	return null


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
	if kind == "map":
		return app.map_id
	if kind == "lobby":
		return "1" if app.lobby != null and app.lobby.visible else "0"
	if kind == "fight":
		return "1" if app.session != null else "0"
	if kind == "remap":
		return "1" if app.remap_screen != null and app.remap_screen.visible else "0"
	if kind == "remap_back":
		return "1" if app.remap_screen != null and app.remap_screen.visible else "0"
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


static func _horiz_sep(a: Fighter, b: Fighter) -> float:
	if a == null or b == null:
		return 999.0
	return absf(a.global_position.x - b.global_position.x)


static func _typed_hold_slot(app: App, key: Key, ticks: int) -> void:
	_typed_hold_keys(app, [key], ticks)


static func _typed_hold_keys(app: App, keys: Array, ticks: int) -> void:
	if app == null or app.session == null or ticks <= 0 or keys.is_empty():
		return
	var vp: Viewport = app.get_viewport()
	var i: int = 0
	while i < keys.size():
		InputInjector.inject_key(keys[i] as Key, true, vp)
		used_parse_input_event += 1
		i += 1
	var n: int = 0
	while n < ticks and app.session != null and app.session.outcome == "play":
		_apply_live_both(app.session)
		n += 1
	i = 0
	while i < keys.size():
		InputInjector.inject_key(keys[i] as Key, false, vp)
		used_parse_input_event += 1
		i += 1
	if app.session != null and app.session.outcome == "play":
		_apply_live_both(app.session)
	InputActions.reset_edges()


static func _typed_tap(app: App, key: Key) -> void:
	_typed_tap_keys(app, [key])


static func _typed_tap_keys(app: App, keys: Array) -> void:
	if app == null or app.session == null or keys.is_empty():
		return
	var vp: Viewport = app.get_viewport()
	var i: int = 0
	while i < keys.size():
		InputInjector.inject_key(keys[i] as Key, true, vp)
		used_parse_input_event += 1
		i += 1
	_apply_live_both(app.session)
	i = 0
	while i < keys.size():
		InputInjector.inject_key(keys[i] as Key, false, vp)
		used_parse_input_event += 1
		i += 1
	if app.session != null and app.session.outcome == "play":
		_apply_live_both(app.session)
	InputActions.reset_edges()


static func _typed_idle(app: App, ticks: int) -> void:
	var n: int = 0
	while n < ticks and app != null and app.session != null and app.session.outcome == "play":
		_apply_live_both(app.session)
		n += 1


static func _apply_live_both(session: GameSession) -> void:
	if session == null:
		return
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and f.is_human:
			frames.append(InputActions.read_player_frame(f.slot, session.clock.tick))
		else:
			frames.append(InputFrame.from_dict(InputActions.empty_frame(session.clock.tick, i)))
		i += 1
	used_apply_frames_attempted += 1
	if session.apply_frames(frames):
		used_apply_frames_succeeded += 1
		used_apply_frames += 1


static func _ui_frames(app: App) -> void:
	if app == null or app.get_tree() == null:
		return
	var tree: SceneTree = app.get_tree()
	await tree.process_frame
	await tree.process_frame


static func _click_control(app: App, ctrl: Control) -> void:
	if app == null or ctrl == null or app.get_viewport() == null:
		return
	var pos: Vector2 = ctrl.get_global_transform_with_canvas().origin + ctrl.size * 0.5
	var down: InputEventMouseButton = InputEventMouseButton.new()
	down.button_index = MOUSE_BUTTON_LEFT
	down.pressed = true
	down.position = pos
	down.global_position = pos
	app.get_viewport().push_input(down)
	var up: InputEventMouseButton = InputEventMouseButton.new()
	up.button_index = MOUSE_BUTTON_LEFT
	up.pressed = false
	up.position = pos
	up.global_position = pos
	app.get_viewport().push_input(up)


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
	print("HH_VF_VS2 SCREENSHOT_%s err=%d path=%s" % [stem, int(err), shot])
	return shot


static func _note(name: String, actions: int, msec: float) -> void:
	timeline.append({
		"name": name,
		"actions": actions,
		"ms": msec,
	})
	print("HH_VF_VS2 TIMELINE name=%s actions=%d ms=%d" % [name, actions, int(msec)])


static func _append_events(rows: Array) -> void:
	var i: int = 0
	while i < rows.size():
		events_all.append(rows[i])
		i += 1


static func _append(into: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		into.append(String(extra[i]))
		i += 1
