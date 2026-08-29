class_name SimRecorder
extends RefCounted

## Record typed InputFrames from Godot Input (or scripted frames).
## Official output never writes teleport / force_kill.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).

var active: bool = false
var record_source: String = "live_input"
var snapshot_every: int = SimConstants.DEFAULT_SNAPSHOT_EVERY
var mode: String = "vs2"
var map_id: String = "police"
var stage_index: int = 0
var seed_v: int = 0
var trace_name: String = "recorded"
var bundles: Array = []
var hashes: Array = []
var used_fixture: bool = false


func begin(session: GameSession, source: String) -> void:
	active = true
	record_source = source
	bundles.clear()
	hashes.clear()
	used_fixture = false
	if session == null:
		return
	mode = session.mode
	map_id = session.map_id
	stage_index = session.stage_index
	seed_v = session.sim_seed
	_hash_if_due(session, true)


func capture_live_bundle(session: GameSession) -> Array:
	var frames: Array = []
	if session == null:
		return frames
	var tick: int = 0
	if session.clock != null:
		tick = session.clock.tick
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and f.is_human:
			frames.append(InputActions.read_player_frame(f.slot, tick))
		elif f != null and f.is_bot:
			if i >= session.brains.size():
				session.brains.append(BotBrain.new())
			var cmd: Dictionary = session.brains[i].think(
				f, session.fighters, session.pickups, SimConstants.TICK_DT
			)
			frames.append(InputActions.frame_from_cmd(cmd, tick, i))
		else:
			frames.append(InputFrame.from_dict(InputActions.empty_frame(tick, i)))
		i += 1
	return frames


func record_live_tick(session: GameSession) -> bool:
	if session == null or not active:
		return false
	var frames: Array = capture_live_bundle(session)
	return _store_and_apply(session, frames)


func record_scripted_tick(session: GameSession, frames: Array) -> bool:
	if session == null or not active:
		return false
	return _store_and_apply(session, frames)


func step_session(session: GameSession) -> bool:
	return record_live_tick(session)


func finish() -> Dictionary:
	active = false
	return to_trace_dict()


func to_trace_dict() -> Dictionary:
	var kind: String = "fixture" if used_fixture else "official"
	var frames_out: Array = []
	var i: int = 0
	while i < bundles.size():
		var slots_raw: Array = bundles[i] as Array
		var slots: Array = []
		var s: int = 0
		while s < slots_raw.size():
			var raw: Variant = slots_raw[s]
			if raw is InputFrame:
				slots.append((raw as InputFrame).to_dict())
			elif raw is Dictionary:
				slots.append(raw)
			s += 1
		frames_out.append({
			"tick": i,
			"slots": slots,
		})
		i += 1
	return {
		"schema": SimConstants.TRACE_ID,
		"schema_version": SimConstants.SCHEMA_VERSION,
		"title": "Vault Fighters",
		"kind": kind,
		"name": trace_name,
		"record_source": record_source,
		"mode": mode,
		"map_id": map_id,
		"stage_index": stage_index,
		"seed": seed_v,
		"fighter_count": _slot_count(),
		"tick_hz": SimConstants.TICK_HZ,
		"snapshot_every": snapshot_every,
		"ledger_clock": "RL-SIM-FIXED-60",
		"y8_tick_rate_claimed": false,
		"y8_parity_claimed": false,
		"hold_to_aim": "RL-CTRL-HOLD-AIM assumption, not observed",
		"roll": "RL-MOVE-ROLL assumption, not observed",
		"sprint": "RL-MOVE-SPRINT assumption, not observed",
		"roll_dive": "RL-MOVE-ROLL-DIVE dive/kick unavailable",
		"frames": frames_out,
		"hashes": hashes.duplicate(true),
	}


func _store_and_apply(session: GameSession, frames: Array) -> bool:
	var typed: Array = SimTrace.to_input_frames(frames)
	bundles.append(typed)
	var ok: bool = session.apply_frames(typed)
	if ok:
		_hash_if_due(session, false)
	return ok


func _hash_if_due(session: GameSession, force: bool) -> void:
	if session == null:
		return
	var tick: int = 0
	if session.clock != null:
		tick = session.clock.tick
	if force or tick == 0 or tick % snapshot_every == 0:
		hashes.append({
			"tick": tick,
			"hash": session.snapshot_hash(),
		})


func _slot_count() -> int:
	if bundles.is_empty():
		return 0
	var first: Array = bundles[0] as Array
	return first.size()
