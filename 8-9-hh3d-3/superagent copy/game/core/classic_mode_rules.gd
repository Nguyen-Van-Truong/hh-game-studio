class_name ClassicModeRules
extends RefCounted
## Deterministic match-flow authority for the observed Classic mode families.
## This is a clean-room implementation slice; it does not claim reference parity.

const SCHEMA: StringName = &"sa07.mode-rules.v1"
const STAGE_COUNT: int = 12
const SURVIVAL_START_WAVE: int = 0

var mode: StringName = &"vs"
var rule: StringName = &"infinite"
var phase: StringName = &"ready"
var round_index: int = 0
var score: Array[int] = [0, 0]
var target_score: int = 0
var stage_index: int = 0
var unlocked_stages: Array[bool] = []
var survival_wave: int = SURVIVAL_START_WAVE
var pause_requested: bool = false
var last_winner: int = 0
var error: StringName = &""

func _init(mode_input: StringName = &"vs", rule_input: StringName = &"infinite") -> void:
	_reset_stage_unlocks()
	configure(mode_input, rule_input)

func configure(mode_input: StringName, rule_input: StringName = &"infinite") -> bool:
	_reset_runtime_state()
	mode = &"vs"
	rule = &"infinite"
	target_score = 0
	var normalized_mode: StringName = _normalize_mode(mode_input)
	if normalized_mode == &"":
		error = &"unknown_mode"
		phase = &"invalid"
		return false
	var normalized_rule: StringName = _normalize_rule(rule_input)
	if normalized_mode != &"vs":
		normalized_rule = &"infinite"
	if normalized_mode == &"vs" and normalized_rule == &"":
		error = &"unknown_vs_rule"
		phase = &"invalid"
		return false
	mode = normalized_mode
	rule = normalized_rule
	target_score = _target_for_rule(mode, rule)
	phase = &"ready"
	_reset_stage_unlocks()
	return true

func begin() -> bool:
	if phase == &"invalid":
		return false
	if phase == &"ready" or phase == &"round_result":
		phase = &"playing"
		pause_requested = false
		return true
	return phase == &"playing" or phase == &"paused"

func set_paused(value: bool) -> bool:
	if value and phase != &"playing":
		return false
	if not value and phase != &"paused":
		return false
	pause_requested = value
	phase = &"paused" if value else &"playing"
	return true

func record_round(winner: int) -> bool:
	if phase != &"playing" or winner < 0 or winner > 2:
		return false
	last_winner = winner
	round_index += 1
	if mode == &"survival":
		if winner != 1:
			phase = &"result"
			return true
		survival_wave += 1
		phase = &"round_result"
		return true
	if mode == &"stage":
		if winner == 1:
			unlocked_stages[stage_index] = true
			if stage_index < STAGE_COUNT - 1:
				unlocked_stages[stage_index + 1] = true
				stage_index += 1
				phase = &"round_result"
			else:
				phase = &"result"
		else:
			phase = &"result"
		return true
	if winner > 0:
		score[winner - 1] += 1
	if rule == &"infinite":
		phase = &"result"
		return true
	if _vs_complete():
		phase = &"result"
	else:
		phase = &"round_result"
	return true

func next_round() -> bool:
	if phase != &"round_result":
		return false
	phase = &"playing"
	pause_requested = false
	return true

func reset_for_rematch() -> void:
	round_index = 0
	score = [0, 0]
	stage_index = 0
	survival_wave = SURVIVAL_START_WAVE
	last_winner = 0
	pause_requested = false
	error = &""
	phase = &"ready"
	_reset_stage_unlocks()

func is_stage_unlocked(index: int) -> bool:
	return index >= 0 and index < unlocked_stages.size() and unlocked_stages[index]

func snapshot() -> Dictionary:
	var stages: Array[bool] = unlocked_stages.duplicate()
	stages.make_read_only()
	var score_snapshot: Array[int] = score.duplicate()
	score_snapshot.make_read_only()
	var result: Dictionary = {
		&"schema": SCHEMA,
		&"mode": mode,
		&"rule": rule,
		&"phase": phase,
		&"round_index": round_index,
		&"score": score_snapshot,
		&"target_score": target_score,
		&"stage_index": stage_index,
		&"unlocked_stages": stages,
		&"survival_wave": survival_wave,
		&"paused": pause_requested,
		&"last_winner": last_winner,
		&"error": error,
	}
	result.make_read_only()
	return result

func canonical_snapshot() -> String:
	var unlocks: String = "".join(unlocked_stages.map(func(value: bool) -> String: return "1" if value else "0"))
	return "%s|mode=%s|rule=%s|phase=%s|round=%d|score=%d,%d|target=%d|stage=%d|unlocks=%s|wave=%d|paused=%d|last=%d|error=%s" % [
		String(SCHEMA), String(mode), String(rule), String(phase), round_index, score[0], score[1], target_score,
		stage_index, unlocks, survival_wave, int(pause_requested), last_winner, String(error)]

func _vs_complete() -> bool:
	return target_score > 0 and (score[0] >= target_score or score[1] >= target_score)

func _target_for_rule(mode_input: StringName, rule_input: StringName) -> int:
	if mode_input != &"vs" or rule_input == &"infinite":
		return 0
	if rule_input == &"first_to_3" or rule_input == &"best_of_3":
		return 2 if rule_input == &"best_of_3" else 3
	if rule_input == &"first_to_5" or rule_input == &"best_of_5":
		return 3 if rule_input == &"best_of_5" else 5
	if rule_input == &"first_to_10" or rule_input == &"best_of_10":
		return 6 if rule_input == &"best_of_10" else 10
	return 0

func _normalize_mode(value: StringName) -> StringName:
	if value == &"vs" or value == &"stage" or value == &"survival":
		return value
	return &""

func _normalize_rule(value: StringName) -> StringName:
	var allowed: Array[StringName] = [&"infinite", &"first_to_3", &"first_to_5", &"first_to_10", &"best_of_3", &"best_of_5", &"best_of_10"]
	return value if value in allowed else &""

func _reset_stage_unlocks() -> void:
	unlocked_stages.clear()
	for index: int in range(STAGE_COUNT):
		unlocked_stages.append(index == 0)

func _reset_runtime_state() -> void:
	phase = &"ready"
	round_index = 0
	score = [0, 0]
	stage_index = 0
	survival_wave = SURVIVAL_START_WAVE
	pause_requested = false
	last_winner = 0
	error = &""
	_reset_stage_unlocks()
