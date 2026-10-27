extends SceneTree
## Provisional SA-07 MatchSession mode seam checks. These exercise the
## constructor and round transition without claiming reference parity.

const MATCH_SCRIPT = preload("res://game/core/match_session.gd")
const INPUT_SCRIPT = preload("res://game/core/input_frame.gd")
const FIXTURE_SCRIPT = preload("res://tests/physics_fixture.gd")

var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var invalid: MatchSession = MATCH_SCRIPT.new(3, &"two_player", &"unknown", &"infinite")
	_expect(invalid.phase == &"invalid" and invalid.error == &"unknown_mode", "invalid mode fails closed at session construction")
	invalid.free()
	var session: MatchSession = MATCH_SCRIPT.new(4, &"two_player", &"vs", &"best_of_3")
	var viewport := SubViewport.new()
	viewport.name = "MatchModeFixture"
	viewport.size = Vector2i(1600, 900)
	viewport.world_2d = World2D.new()
	viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	viewport.add_to_group(FIXTURE_SCRIPT.FIXTURE_GROUP)
	root.add_child(viewport)
	viewport.add_child(session)
	await process_frame
	_expect(session.phase == &"playing" and session.mode_rules.phase == &"playing", "valid session starts both match and rules in playing")
	session.fighters[1].health = 0
	await physics_frame
	_expect(session.step(_empty_frame(session.tick)), "lethal round advances through fixed-step session")
	_expect(session.phase == &"round_result" and session.mode_rules.phase == &"round_result", "non-terminal VS round exposes round_result in both layers")
	var prior_tick: int = session.tick
	_expect(session.continue_round(), "round_result can continue into a fresh round")
	_expect(session.phase == &"playing" and session.mode_rules.phase == &"playing", "continue_round resumes both layers")
	_expect(session.round_timer_ticks == 0 and session.tick == prior_tick, "continue_round resets per-round timer without rewinding match tick")
	_expect(session.fighters[0].health == 100 and session.fighters[0].facing == 1, "continue_round resets fighter resources and facing")
	_expect(session.set_paused(true), "session pause enters through mode rules")
	var mode_snapshot: Dictionary = session.snapshot().get(&"mode_rules", {})
	_expect(session.phase == &"paused" and session.mode_rules.phase == &"paused" and bool(mode_snapshot.get(&"paused", false)), "pause is reflected in both snapshots")
	_expect(session.set_paused(false) and session.phase == &"playing" and session.mode_rules.phase == &"playing", "session resume restores both layers")
	await FIXTURE_SCRIPT.cleanup(self)
	await _run_stage_session()
	await _run_survival_session()
	print("SA-07 match modes PASS: %d assertions" % assertions)
	quit()

func _run_stage_session() -> void:
	var viewport := _new_viewport("StageModeFixture")
	var stage: MatchSession = MATCH_SCRIPT.new(5, &"two_player", &"stage", &"infinite")
	viewport.add_child(stage)
	await process_frame
	for index: int in range(12):
		stage.fighters[1].health = 0
		await physics_frame
		_expect(stage.step(_empty_frame(stage.tick)), "stage round %d advances" % (index + 1))
		if index < 11:
			_expect(stage.phase == &"round_result" and stage.continue_round(), "stage round %d continues" % (index + 1))
		else:
			_expect(stage.phase == &"result" and stage.mode_rules.stage_index == 11, "final stage round ends campaign")
	await FIXTURE_SCRIPT.cleanup(self)

func _run_survival_session() -> void:
	var viewport := _new_viewport("SurvivalModeFixture")
	var survival: MatchSession = MATCH_SCRIPT.new(6, &"two_player", &"survival", &"infinite")
	viewport.add_child(survival)
	await process_frame
	survival.fighters[1].health = 0
	await physics_frame
	_expect(survival.step(_empty_frame(survival.tick)), "survival clear advances")
	_expect(survival.phase == &"round_result" and survival.mode_rules.survival_wave == 1, "survival clear advances wave")
	_expect(survival.continue_round(), "survival starts the next wave")
	survival.fighters[0].health = 0
	await physics_frame
	_expect(survival.step(_empty_frame(survival.tick)), "survival defeat advances")
	_expect(survival.phase == &"result" and survival.mode_rules.last_winner == 2, "survival P2 defeat ends session")
	await FIXTURE_SCRIPT.cleanup(self)

func _new_viewport(name: StringName) -> SubViewport:
	var viewport := SubViewport.new()
	viewport.name = name
	viewport.size = Vector2i(1600, 900)
	viewport.world_2d = World2D.new()
	viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	viewport.add_to_group(FIXTURE_SCRIPT.FIXTURE_GROUP)
	root.add_child(viewport)
	return viewport

func _empty_frame(frame_tick: int) -> InputFrame:
	var records: Array[Dictionary] = []
	for action: StringName in INPUT_SCRIPT.ACTIONS:
		var player: int = 1 if String(action).begins_with("p1_") else 2
		records.append({
			&"schema_version": INPUT_SCRIPT.SCHEMA_VERSION,
			&"tick": frame_tick,
			&"player": player,
			&"action": action,
			&"initial_held": false,
			&"events": [],
			&"pressed": false,
			&"held": false,
			&"released": false,
		})
	return INPUT_SCRIPT.create(frame_tick, records)

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		push_error("FAIL: " + message)
		quit(1)
