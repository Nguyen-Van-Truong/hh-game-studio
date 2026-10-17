extends SceneTree

const RULES_SCRIPT = preload("res://game/core/classic_mode_rules.gd")
var assertions: int = 0

func _init() -> void:
	var best: ClassicModeRules = RULES_SCRIPT.new(&"vs", &"best_of_3")
	_expect(best.begin(), "best-of-3 begins")
	_expect(best.target_score == 2, "best-of-3 target is two round wins")
	_expect(best.record_round(1), "first round is recorded")
	_expect(best.phase == &"round_result" and best.score == [1, 0], "first round waits for next-round transition")
	_expect(best.next_round() and best.phase == &"playing", "next round resumes play")
	_expect(best.record_round(2) and best.next_round(), "second round records and resumes")
	_expect(best.record_round(1), "deciding round is recorded")
	_expect(best.phase == &"result" and best.score == [2, 1], "best-of-3 ends at two wins")
	_expect(not best.next_round(), "completed match cannot silently continue")

	var stage: ClassicModeRules = RULES_SCRIPT.new(&"stage", &"ignored")
	_expect(stage.is_stage_unlocked(0) and not stage.is_stage_unlocked(1), "stage starts with only first challenge")
	_expect(stage.begin() and stage.record_round(1), "stage win records")
	_expect(stage.stage_index == 1 and stage.is_stage_unlocked(1), "stage win unlocks the next challenge")
	_expect(stage.next_round() and stage.record_round(2), "stage loss records a terminal result")
	_expect(stage.phase == &"result" and stage.stage_index == 1, "stage loss does not advance")
	var final_stage: ClassicModeRules = RULES_SCRIPT.new(&"stage", &"ignored")
	_expect(final_stage.begin(), "final stage run begins")
	for index: int in range(11):
		_expect(final_stage.record_round(1), "stage progression win %d records" % index)
		_expect(final_stage.next_round(), "stage progression win %d advances" % index)
	_expect(final_stage.record_round(1), "final stage win records")
	_expect(final_stage.phase == &"result" and final_stage.stage_index == 11, "final stage win ends the campaign")

	var survival: ClassicModeRules = RULES_SCRIPT.new(&"survival", &"ignored")
	_expect(survival.begin() and survival.record_round(1), "survival wave clear records")
	_expect(survival.survival_wave == 1 and survival.phase == &"round_result", "survival advances the wave")
	_expect(survival.next_round() and survival.record_round(0), "survival defeat records")
	_expect(survival.phase == &"result", "survival defeat ends the run")
	var survival_p2: ClassicModeRules = RULES_SCRIPT.new(&"survival", &"ignored")
	_expect(survival_p2.begin() and survival_p2.record_round(2), "survival P2 defeat records")
	_expect(survival_p2.phase == &"result", "survival P2 defeat ends the run")

	var paused: ClassicModeRules = RULES_SCRIPT.new()
	_expect(paused.begin() and paused.set_paused(true), "pause enters paused phase")
	_expect(paused.phase == &"paused" and paused.snapshot()[&"paused"], "pause is represented in snapshot")
	_expect(paused.set_paused(false) and paused.phase == &"playing", "resume returns to playing")
	var score_snapshot: Variant = best.snapshot()[&"score"]
	var score_array: Array = score_snapshot if score_snapshot is Array else []
	_expect(score_snapshot is Array and score_array.is_read_only(), "mode score snapshot is immutable")
	var reconfigured: ClassicModeRules = RULES_SCRIPT.new(&"vs", &"best_of_3")
	_expect(reconfigured.begin() and reconfigured.record_round(1), "reconfigure fixture starts")
	_expect(not reconfigured.configure(&"unknown", &"best_of_3"), "invalid reconfigure fails closed")
	_expect(reconfigured.phase == &"invalid" and reconfigured.score == [0, 0] and reconfigured.error == &"unknown_mode", "invalid reconfigure clears stale state")
	_expect(not RULES_SCRIPT.new(&"unknown", &"infinite").begin(), "unknown mode fails closed")
	print("SA-07 mode rules PASS: %d assertions" % assertions)
	quit()

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		push_error("FAIL: " + message)
		quit(1)
