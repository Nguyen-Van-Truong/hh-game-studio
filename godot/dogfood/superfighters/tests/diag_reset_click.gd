extends SceneTree

## Diagnostic only. Not official. Not in freeze extra.

const StageCasesScript: GDScript = preload("res://tests/stage_cases.gd")
const _Stage: GDScript = preload("res://src/sim/stage.gd")


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	InputActions.install()
	OS.set_environment("HH_VF_STAGE_STORE", "progress_vf6wp3_diag_reset.json")
	_Stage.reset_progress()
	var planted: Dictionary = _Stage.empty_progress()
	planted["current_index"] = 3
	planted["score"] = 30
	planted["awarded"] = [0, 1, 2]
	planted["unlocks"] = ["storage", "police", "hazardous"]
	planted["cleared"] = true
	planted["reward_hash"] = _Stage.compute_hash(planted)
	var saved: String = _Stage.persist_atomic(planted)
	print("HH_DIAG plant path=%s score=%d" % [saved, int(_Stage.load_or_empty().get("score", -1))])
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	await StageCasesScript._ui_frames(app)
	app.restart_to_title()
	await StageCasesScript._ui_frames(app)
	if app.title != null:
		app.title.refresh_stage_caption()
	var before: int = int(_Stage.load_or_empty().get("score", -1))
	print(
		"HH_DIAG title visible=%s phase=%s reset_txt=%s confirm_vis=%s score=%d"
		% [
			str(app.title.visible if app.title != null else false),
			app.flow_phase,
			str(app.title.reset_stage_btn.text if app.title != null else ""),
			str(app.title.confirm_reset_btn.visible if app.title != null else false),
			before,
		]
	)
	var btn: Button = app.title.reset_stage_btn
	var vis: Rect2 = app.get_viewport().get_visible_rect()
	print(
		"HH_DIAG click_target global=%s canvas=%s rect=%s size=%s vis=%s"
		% [
			str(btn.global_position),
			str(btn.get_global_transform_with_canvas().origin),
			str(btn.get_global_rect()),
			str(btn.size),
			str(vis),
		]
	)
	await StageCasesScript._click_control_only(app, btn)
	await StageCasesScript._ui_frames(app)
	var mid_score: int = int(_Stage.load_or_empty().get("score", -2))
	print(
		"HH_DIAG after_reset_click armed=%s confirm_vis=%s confirm_txt=%s score=%d"
		% [
			str(app.title.reset_armed),
			str(app.title.confirm_reset_btn.visible),
			str(app.title.confirm_reset_btn.text),
			mid_score,
		]
	)
	await StageCasesScript._click_control_only(app, app.title.confirm_reset_btn)
	await StageCasesScript._ui_frames(app)
	var wiped: Dictionary = _Stage.load_or_empty()
	print(
		"HH_DIAG after_confirm score=%d idx=%d awarded=%s confirm_vis=%s phase=%s"
		% [
			int(wiped.get("score", -1)),
			int(wiped.get("current_index", -1)),
			str(wiped.get("awarded", [])),
			str(app.title.confirm_reset_btn.visible),
			app.flow_phase,
		]
	)
	var ok: bool = (
		before == 30
		and mid_score == 30
		and int(wiped.get("score", -1)) == 0
		and int(wiped.get("current_index", -1)) == 0
		and app.flow_phase == "title"
		and app.session == null
	)
	print("HH_DIAG RESET_CLICK %s" % ("PASS" if ok else "FAIL"))
	quit(0 if ok else 1)
