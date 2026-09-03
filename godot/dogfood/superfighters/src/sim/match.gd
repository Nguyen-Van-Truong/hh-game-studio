class_name MatchRules
extends RefCounted

## Canonical match state machine for every mode (VF6-WP1).
## Clock is ledger:RL-SIM-FIXED-60 (assumption).
## Last-standing / teams stay ledger:RL-MATCH-LAST / RL-MATCH-TEAMS
## (assumption). Round timer stays ledger:RL-MATCH-TIMER
## (assumption, not observed). Countdown stays
## ledger:RL-MATCH-COUNTDOWN (assumption, not observed).
## Friendly-fire stays ledger:RL-HIT-FF (assumption).
## Official path never calls force_kill / teleport.

const PATH: String = "res://data/sim/match.json"
const SCHEMA_ID: String = "vf.sim.match.v1"
const _Combat: GDScript = preload("res://src/sim/combat.gd")

const PHASE_BOOT: String = "boot"
const PHASE_MENU: String = "menu"
const PHASE_COUNTDOWN: String = "countdown"
const PHASE_ACTIVE: String = "active"
const PHASE_PAUSED: String = "paused"
const PHASE_RESOLVED: String = "resolved"
const PHASE_QUIT: String = "quit"

static var _cache: Dictionary = {}

var phase: String = PHASE_BOOT
var outcome: String = "play"
var end_reason: String = ""
var round_id: int = 0
var spawn_seed: int = 0
var winner_team: int = -1
var timer_enabled: bool = false
var timer_left: int = -1
var countdown_left: int = 0
var alignment: String = "ffa"
var transitions: Array = []
var _emitted: Dictionary = {}
var _resume_phase: String = PHASE_ACTIVE

const _LEGAL: Dictionary = {
	PHASE_BOOT: [PHASE_MENU],
	PHASE_MENU: [PHASE_COUNTDOWN, PHASE_QUIT],
	PHASE_COUNTDOWN: [PHASE_ACTIVE, PHASE_PAUSED, PHASE_QUIT, PHASE_RESOLVED],
	PHASE_ACTIVE: [PHASE_PAUSED, PHASE_RESOLVED, PHASE_QUIT],
	PHASE_PAUSED: [PHASE_ACTIVE, PHASE_QUIT],
	PHASE_RESOLVED: [PHASE_MENU],
	PHASE_QUIT: [PHASE_MENU],
}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func validate() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var row: Dictionary = data()
	if row.is_empty():
		errors.append("missing data/sim/match.json")
		return errors
	if str(row.get("schema", "")) != SCHEMA_ID:
		errors.append("match schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("match title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("match must not claim Y8 parity")
	if bool(row.get("y8_tick_rate_claimed", true)):
		errors.append("match must not claim a Y8 tick rate")
	if str(row.get("machine_class", "")) != "assumption":
		errors.append("match machine must stay assumption")
	if str(row.get("timer_class", "")) != "assumption":
		errors.append("round timer must stay assumption")
	if bool(row.get("timer_observed", true)):
		errors.append("round timer must not be marked observed")
	if not bool(row.get("canonical", false)):
		errors.append("match machine must be canonical")
	var modes: Dictionary = _dict(row.get("modes", {}))
	var required: PackedStringArray = PackedStringArray(["vs1", "vs2", "stage", "survival"])
	var i: int = 0
	while i < required.size():
		var mid: String = String(required[i])
		if not modes.has(mid):
			errors.append("match modes missing %s" % mid)
			i += 1
			continue
		var mode_info: Dictionary = _dict(modes[mid])
		if mid == "survival":
			if not bool(mode_info.get("shipped", false)):
				errors.append("survival must be shipped this WP")
			if not bool(mode_info.get("uses_machine", false)):
				errors.append("survival must use the canonical machine")
			if bool(mode_info.get("official_lifecycle", false)):
				errors.append("survival must not steal official_lifecycle from vs2")
		elif mid == "vs2":
			if not bool(mode_info.get("uses_machine", false)):
				errors.append("mode vs2 must use the canonical machine")
			if not bool(mode_info.get("official_lifecycle", false)):
				errors.append("vs2 is the official lifecycle mode")
		elif not bool(mode_info.get("uses_machine", false)):
			errors.append("mode %s must use the canonical machine when started" % mid)
		i += 1
	if _Combat.friendly_fire_on("vs1") != false:
		errors.append("vs1 friendly_fire must stay false")
	if _Combat.friendly_fire_on("vs2") != true:
		errors.append("vs2 friendly_fire must stay true")
	if _Combat.friendly_fire_on("stage") != false:
		errors.append("stage friendly_fire must stay false")
	if _Combat.friendly_fire_on("survival") != false:
		errors.append("survival friendly_fire must stay false")
	return errors


static func mode_row(mode: String) -> Dictionary:
	return _dict(_dict(data().get("modes", {})).get(mode, {}))


static func alignment_of(mode: String) -> String:
	return str(mode_row(mode).get("alignment", "ffa"))


static func friendly_fire_on(mode: String) -> bool:
	return _Combat.friendly_fire_on(mode)


static func countdown_ticks(test_driven: bool) -> int:
	var row: Dictionary = _dict(data().get("countdown", {}))
	if test_driven and bool(row.get("skip_when_test_driven", true)):
		return 0
	return maxi(int(row.get("ticks", 0)), 0)


static func default_timer_enabled() -> bool:
	return bool(_dict(data().get("round_timer", {})).get("enabled", false))


static func default_timer_ticks() -> int:
	return maxi(int(_dict(data().get("round_timer", {})).get("ticks", 0)), 0)


static func evaluate(
	fighters: Array,
	mode: String,
	p1_slot: int,
	p_timer_enabled: bool,
	p_timer_left: int
) -> Dictionary:
	var p1: Variant = null
	var living_teams: Dictionary = {}
	var living: int = 0
	var i: int = 0
	while i < fighters.size():
		var f: Variant = fighters[i]
		i += 1
		if f == null or not is_instance_valid(f):
			continue
		if f.slot == p1_slot:
			p1 = f
		if not f.dead:
			living += 1
			living_teams[f.team] = int(living_teams.get(f.team, 0)) + 1
	var team_ids: Array = living_teams.keys()
	var p1_team: int = int(p1.team) if p1 != null else 0
	var p1_team_alive: bool = living_teams.has(p1_team)
	if mode == "survival":
		var p1_dead: bool = p1 == null or bool(p1.dead)
		if p1_dead or not p1_team_alive:
			return {
				"outcome": "lose",
				"end_reason": "p1_down",
				"winner_team": -1,
				"living": living,
				"living_teams": team_ids,
				"mode": mode,
			}
		return {
			"outcome": "play",
			"end_reason": "",
			"winner_team": -1,
			"living": living,
			"living_teams": team_ids,
			"mode": mode,
		}
	if living <= 0 or team_ids.is_empty():
		return {
			"outcome": "tie",
			"end_reason": "all_down",
			"winner_team": -1,
			"living": 0,
			"living_teams": team_ids,
			"mode": mode,
		}
	if team_ids.size() == 1:
		if p1_team_alive:
			return {
				"outcome": "win",
				"end_reason": "last_standing",
				"winner_team": int(team_ids[0]),
				"living": living,
				"living_teams": team_ids,
				"mode": mode,
			}
		return {
			"outcome": "lose",
			"end_reason": "p1_down",
			"winner_team": int(team_ids[0]),
			"living": living,
			"living_teams": team_ids,
			"mode": mode,
		}
	if not p1_team_alive:
		return {
			"outcome": "lose",
			"end_reason": "p1_down",
			"winner_team": -1,
			"living": living,
			"living_teams": team_ids,
			"mode": mode,
		}
	if p_timer_enabled and p_timer_left <= 0:
		return {
			"outcome": "tie",
			"end_reason": "timeout",
			"winner_team": -1,
			"living": living,
			"living_teams": team_ids,
			"mode": mode,
		}
	return {
		"outcome": "play",
		"end_reason": "",
		"winner_team": -1,
		"living": living,
		"living_teams": team_ids,
		"mode": mode,
	}


func reset() -> void:
	phase = PHASE_BOOT
	outcome = "play"
	end_reason = ""
	winner_team = -1
	timer_enabled = default_timer_enabled()
	timer_left = default_timer_ticks() if timer_enabled else -1
	countdown_left = 0
	alignment = "ffa"
	transitions.clear()
	_emitted = {
		"win": false,
		"lose": false,
		"tie": false,
		"quit": false,
	}
	_resume_phase = PHASE_ACTIVE


func begin(session: Variant, p_round_id: int) -> void:
	reset()
	round_id = p_round_id
	if session != null:
		spawn_seed = session.sim_seed
		alignment = alignment_of(session.mode)
		session.outcome = "play"
	_record(session, PHASE_BOOT, PHASE_MENU, "boot")
	phase = PHASE_MENU
	var count: int = 0
	if session != null:
		count = countdown_ticks(session.test_driven)
	countdown_left = count
	_record(session, PHASE_MENU, PHASE_COUNTDOWN, "countdown")
	phase = PHASE_COUNTDOWN
	if countdown_left <= 0:
		ensure_active(session)


func enable_timer(ticks: int) -> void:
	timer_enabled = ticks > 0
	timer_left = ticks if timer_enabled else -1


func tick_countdown(session: Variant) -> void:
	if phase != PHASE_COUNTDOWN:
		return
	if countdown_left > 0:
		countdown_left -= 1
	if countdown_left <= 0:
		ensure_active(session)


func ensure_active(session: Variant) -> void:
	if phase == PHASE_ACTIVE:
		return
	if phase == PHASE_COUNTDOWN and countdown_left <= 0:
		_enter_active(session)


func enter_pause(session: Variant) -> void:
	if not _can_transition(PHASE_PAUSED):
		return
	_resume_phase = PHASE_ACTIVE
	_record(session, PHASE_ACTIVE, PHASE_PAUSED, "pause")
	phase = PHASE_PAUSED


func leave_pause(session: Variant) -> void:
	if not _can_transition(_resume_phase):
		return
	_record(session, PHASE_PAUSED, _resume_phase, "resume")
	phase = _resume_phase


func request_quit(session: Variant) -> void:
	if (outcome != "play" and outcome != "quit") or not _can_transition(PHASE_QUIT):
		return
	if _emitted.get("quit", false):
		return
	outcome = "quit"
	end_reason = "quit"
	winner_team = -1
	if session != null:
		session.outcome = "quit"
	_record(session, phase, PHASE_QUIT, "quit")
	phase = PHASE_QUIT
	_emit_once(session)


func apply_eval(session: Variant, eval: Dictionary) -> void:
	if outcome != "play" or not _can_transition(PHASE_RESOLVED):
		return
	var next: String = str(eval.get("outcome", "play"))
	if next == "play" or next == "":
		return
	outcome = next
	end_reason = str(eval.get("end_reason", ""))
	winner_team = int(eval.get("winner_team", -1))
	if session != null:
		session.outcome = next
		if next == "win":
			session.win_title = "Last standing"
		elif next == "lose":
			session.lose_title = "Down"
	_record(session, phase, PHASE_RESOLVED, end_reason)
	phase = PHASE_RESOLVED
	_emit_once(session)


func snapshot_row(session: Variant) -> Dictionary:
	var tick: int = 0
	var digest: String = ""
	if session != null:
		if session.clock != null:
			tick = session.clock.tick
		digest = session.snapshot_hash()
	return {
		"round_id": round_id,
		"phase": phase,
		"outcome": outcome,
		"end_reason": end_reason,
		"winner_team": winner_team,
		"spawn_seed": spawn_seed,
		"alignment": alignment,
		"timer_enabled": 1 if timer_enabled else 0,
		"timer_left": timer_left,
		"countdown_left": countdown_left,
		"tick": tick,
		"hash": digest,
		"emitted_win": 1 if bool(_emitted.get("win", false)) else 0,
		"emitted_lose": 1 if bool(_emitted.get("lose", false)) else 0,
		"emitted_tie": 1 if bool(_emitted.get("tie", false)) else 0,
		"emitted_quit": 1 if bool(_emitted.get("quit", false)) else 0,
		"transition_count": transitions.size(),
	}


func validate_state() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if not _LEGAL.has(phase):
		errors.append("unknown match phase %s" % phase)
	if phase == PHASE_RESOLVED and not ["win", "lose", "tie"].has(outcome):
		errors.append("resolved phase requires terminal outcome")
	if phase == PHASE_QUIT and outcome != "quit":
		errors.append("quit phase requires quit outcome")
	if outcome == "play" and phase in [PHASE_RESOLVED, PHASE_QUIT]:
		errors.append("play outcome cannot be terminal")
	if round_id < 0:
		errors.append("round_id must be non-negative")
	return errors


func emitted_count() -> int:
	var n: int = 0
	if bool(_emitted.get("win", false)):
		n += 1
	if bool(_emitted.get("lose", false)):
		n += 1
	if bool(_emitted.get("tie", false)):
		n += 1
	if bool(_emitted.get("quit", false)):
		n += 1
	return n


func _enter_active(session: Variant) -> void:
	if phase == PHASE_ACTIVE or not _can_transition(PHASE_ACTIVE):
		return
	countdown_left = 0
	_record(session, phase, PHASE_ACTIVE, "active")
	phase = PHASE_ACTIVE


func _emit_once(session: Variant) -> void:
	if session == null:
		return
	if outcome == "win":
		if bool(_emitted.get("win", false)):
			return
		_emitted["win"] = true
		session.won.emit()
		return
	if outcome == "lose":
		if bool(_emitted.get("lose", false)):
			return
		_emitted["lose"] = true
		session.lost.emit()
		return
	if outcome == "tie":
		if bool(_emitted.get("tie", false)):
			return
		_emitted["tie"] = true
		session.tied.emit()
		return
	if outcome == "quit":
		if bool(_emitted.get("quit", false)):
			return
		_emitted["quit"] = true
		session.quit_match.emit()


func _record(session: Variant, from_phase: String, to_phase: String, reason: String) -> void:
	# Record the post-transition state. Callers may assign phase immediately
	# after this function for compatibility; setting it here guarantees hashes
	# and snapshots describe the destination phase, never the source phase.
	phase = to_phase
	var tick: int = 0
	var digest: String = ""
	var match_digest: String = ""
	if session != null:
		if session.clock != null:
			tick = session.clock.tick
		digest = session.snapshot_hash()
		match_digest = session.match_hash()
		if session.ledger != null:
			session.ledger.push(tick, "match_phase", "transition", {
				"from": from_phase,
				"to": to_phase,
				"reason": reason,
				"round_id": round_id,
				"outcome": outcome,
				"end_reason": end_reason,
				"seed": spawn_seed,
				"post_hash": digest,
				"post_phase": phase,
				"match_hash": match_digest,
			})
	transitions.append({
		"from": from_phase,
		"to": to_phase,
		"reason": reason,
		"tick": tick,
		"hash": digest,
		"match_hash": match_digest,
		"post_phase": phase,
		"outcome": outcome,
		"end_reason": end_reason,
		"round_id": round_id,
	})


func _can_transition(to_phase: String) -> bool:
	if to_phase == phase:
		return false
	var allowed: Array = _LEGAL.get(phase, []) as Array
	return allowed.has(to_phase)


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}
