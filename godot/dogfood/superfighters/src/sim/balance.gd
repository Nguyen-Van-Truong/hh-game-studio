class_name Balance
extends RefCounted

## Seed-controlled crit / knock jitter / spread jitter, damage caps,
## and stamina rationale. Clock is ledger:RL-SIM-FIXED-60 (assumption).
## Chaos stays ledger:RL-MODE-CHAOS (assumption, not observed).
## Crit stays ledger:RL-BAL-CRIT (assumption).
## Knock jitter stays ledger:RL-BAL-KNOCK-JITTER (assumption).
## Spread jitter stays ledger:RL-BAL-SPREAD-RNG (assumption).
## Caps stay ledger:RL-BAL-CAP (assumption).
## Stamina stays ledger:RL-BAL-STAMINA (assumption).
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Y8 observation stays ledger:RL-MOVE-ROLL-DIVE (unavailable).
## Values are product tuning. Not a copied stat table. Not Y8 play.

const PATH: String = "res://data/sim/balance.json"
const SCHEMA_ID: String = "vf.sim.balance.v1"
const _Combat: GDScript = preload("res://src/sim/combat.gd")
const _Aim: GDScript = preload("res://src/sim/aim.gd")
const _Expl: GDScript = preload("res://src/sim/explosive.gd")
const _Roster: GDScript = preload("res://src/data/weapons/roster.gd")

static var _cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func validate() -> PackedStringArray:
	return validate_payload(data())


static func validate_payload(payload: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if payload.is_empty():
		errors.append("balance payload empty")
		return errors
	if str(payload.get("schema", "")) != SCHEMA_ID:
		errors.append("balance schema must be %s" % SCHEMA_ID)
	if str(payload.get("title", "")) != "Vault Fighters":
		errors.append("balance title must be Vault Fighters")
	if bool(payload.get("y8_parity_claimed", true)):
		errors.append("balance must not claim Y8 parity")
	if bool(payload.get("original_exact_numbers_claimed", true)):
		errors.append("balance must not claim original exact numbers")
	if bool(payload.get("copied_stat_table", true)):
		errors.append("balance must not ship a copied stat table")
	if str(payload.get("chaos_class", "")) != "assumption":
		errors.append("chaos must stay assumption")
	if str(payload.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if int(payload.get("scenario_count", 0)) < 1000:
		errors.append("scenario_count must be >= 1000")
	var crit: Dictionary = _dict(payload.get("crit", {}))
	var chance: float = float(crit.get("chance", -1.0))
	if chance < 0.0 or chance > 0.45:
		errors.append("crit chance out of bounded range")
	var mult: float = float(crit.get("multiplier", 0.0))
	if mult < 1.0 or mult > 2.0:
		errors.append("crit multiplier out of bounded range")
	var caps: Dictionary = _dict(payload.get("caps", {}))
	if float(caps.get("hit", 0.0)) < 42.0:
		errors.append("hit cap must cover existing nade/launcher hits")
	if float(caps.get("tick", 0.0)) < float(caps.get("hit", 0.0)):
		errors.append("tick cap must be >= hit cap")
	var stam: Dictionary = _dict(payload.get("stamina", {}))
	for key in ["sprint_drain", "recover", "roll_cost", "dive_cost"]:
		if float(stam.get(key, -1.0)) <= 0.0:
			errors.append("stamina %s must be positive" % key)
	if str(stam.get("rationale", "")).strip_edges() == "":
		errors.append("stamina rationale missing")
	var dom: Dictionary = _dict(payload.get("dominance", {}))
	if float(dom.get("max_win_rate", 1.0)) > 0.5501:
		errors.append("dominance max_win_rate must stay at the published 0.55 bar")
	if int(dom.get("require_distinct_winners", 0)) < 2:
		errors.append("dominance must require >=2 batch winners")
	if int(dom.get("require_distinct_contexts", 0)) < 3:
		errors.append("dominance must require >=3 distinct context_best")
	if bool(dom.get("hardcoded_winners", true)) or bool(dom.get("hardcoded_winner_ids", true)):
		errors.append("dominance must not hard-code winner ids")
	if str(dom.get("method", "")) != "formula_rolls":
		errors.append("dominance method must stay formula_rolls")
	var contexts: Dictionary = _dict(payload.get("contexts", {}))
	var ctx_ids: PackedStringArray = PackedStringArray([
		"close_melee", "high_ground", "pit", "grenade_chain", "friendly_fire"
	])
	var ci: int = 0
	while ci < ctx_ids.size():
		var cid: String = String(ctx_ids[ci])
		var crow: Dictionary = _dict(contexts.get(cid, {}))
		if crow.is_empty():
			errors.append("context %s missing slot fitness" % cid)
		ci += 1
	var overcap: Dictionary = _dict(payload.get("overcap", {}))
	if str(overcap.get("weapon_id", "")) == "":
		errors.append("overcap weapon_id missing")
	if bool(overcap.get("in_spawn_pool", true)):
		errors.append("overcap weapon must stay out of the spawn pool")
	var fixtures: Dictionary = _dict(payload.get("fixtures", {}))
	var required: PackedStringArray = PackedStringArray([
		"fx_balance_melee", "fx_balance_high", "fx_balance_pit",
		"fx_balance_chain", "fx_balance_ff"
	])
	var i: int = 0
	while i < required.size():
		var fid: String = String(required[i])
		if not fixtures.has(fid):
			errors.append("missing fixture %s" % fid)
		else:
			_append(errors, _fixture_has_no_one_way(fid, fixtures.get(fid)))
		i += 1
	return errors


static func crit_chance() -> float:
	return float(_dict(data().get("crit", {})).get("chance", 0.12))


static func crit_multiplier() -> float:
	return float(_dict(data().get("crit", {})).get("multiplier", 1.35))


static func knock_jitter() -> float:
	return float(_dict(data().get("knock", {})).get("jitter", 0.18))


static func spread_jitter() -> float:
	return float(_dict(data().get("spread", {})).get("jitter", 0.55))


static func hit_cap() -> float:
	return float(_dict(data().get("caps", {})).get("hit", 56.0))


static func tick_cap() -> float:
	return float(_dict(data().get("caps", {})).get("tick", 80.0))


static func knock_cap() -> float:
	return float(_dict(data().get("caps", {})).get("knock", 240.0))


static func chaos_salt() -> int:
	return int(data().get("chaos_salt", 10007))


static func scenario_count() -> int:
	return maxi(int(data().get("scenario_count", 1000)), 1000)


static func stamina() -> Dictionary:
	return _dict(data().get("stamina", {}))


static func is_finite_number(value: float) -> bool:
	return is_finite(value) and not is_nan(value)


static func clamp_hit(amount: float) -> float:
	if not is_finite_number(amount):
		return 0.0
	if amount < 0.0:
		return 0.0
	return minf(amount, hit_cap())


static func tick_room(already: float) -> float:
	if not is_finite_number(already):
		return 0.0
	return maxf(0.0, tick_cap() - already)


static func make_stream(seed_v: int, salt: int = 0) -> RandomNumberGenerator:
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	var mixed: int = seed_v + chaos_salt() + salt
	if mixed < 0:
		mixed = 0
	rng.seed = mixed
	return rng


static func roll_hit(rng: RandomNumberGenerator, enabled: bool, base_damage: float, base_knock: Vector2) -> Dictionary:
	var out: Dictionary = {
		"raw": base_damage,
		"damage": clamp_hit(base_damage),
		"knock": _clamp_knock(base_knock),
		"crit": false,
		"finite": true,
	}
	if not is_finite_number(base_damage) or not is_finite_number(base_knock.x) or not is_finite_number(base_knock.y):
		out["raw"] = 0.0
		out["damage"] = 0.0
		out["knock"] = Vector2.ZERO
		out["finite"] = false
		return out
	if not enabled or rng == null:
		return out
	var crit: bool = rng.randf() < crit_chance()
	var raw: float = base_damage
	if crit:
		raw = base_damage * crit_multiplier()
	var j: float = 1.0 + (rng.randf() * 2.0 - 1.0) * knock_jitter()
	var knock: Vector2 = _clamp_knock(base_knock * j)
	out["raw"] = raw
	out["damage"] = clamp_hit(raw)
	out["knock"] = knock
	out["crit"] = crit
	out["finite"] = is_finite_number(raw) and is_finite_number(knock.x) and is_finite_number(knock.y)
	return out


static func jitter_dir(rng: RandomNumberGenerator, dir: Vector2, spread_rad: float, enabled: bool) -> Vector2:
	var out: Vector2 = dir
	if out == Vector2.ZERO:
		out = Vector2.RIGHT
	out = out.normalized()
	if not enabled or rng == null or spread_rad == 0.0:
		return out
	var ang: float = (rng.randf() * 2.0 - 1.0) * spread_rad * spread_jitter()
	out = out.rotated(ang)
	if not is_finite_number(out.x) or not is_finite_number(out.y):
		return dir.normalized() if dir != Vector2.ZERO else Vector2.RIGHT
	return out


static func roll_weapon(rng: RandomNumberGenerator, weapon_id: String, enabled: bool) -> Dictionary:
	var base: Dictionary = _base_weapon(weapon_id)
	var hit: Dictionary = roll_hit(
		rng,
		enabled,
		float(base.get("damage", 0.0)),
		base.get("knock", Vector2.ZERO) as Vector2
	)
	var spread: float = float(base.get("spread", 0.0))
	var dir: Vector2 = jitter_dir(rng, Vector2.RIGHT, spread, enabled)
	hit["weapon"] = weapon_id
	hit["slot"] = str(base.get("slot", ""))
	hit["spread_x"] = dir.x
	hit["spread_y"] = dir.y
	hit["rate"] = float(base.get("rate", 1.0))
	return hit


static func context_mult(slot: String, context: String) -> float:
	var mapped: String = slot
	if mapped == "nade" or mapped == "throw":
		mapped = "explosive"
	if mapped == "gun":
		mapped = "firearm"
	var row: Dictionary = _dict(_dict(data().get("contexts", {})).get(context, {}))
	if row.has(mapped):
		return float(row.get(mapped, 1.0))
	return 1.0


static func score_roll(_weapon_id: String, context: String, roll: Dictionary) -> float:
	# Formula-roll combat score. Slot context fitness is published in
	# docs/balance.md. Winner ids are not hard-coded.
	var dmg: float = float(roll.get("damage", 0.0))
	var knock: Vector2 = roll.get("knock", Vector2.ZERO) as Vector2
	var knock_mag: float = knock.length()
	var rate: float = maxf(float(roll.get("rate", 1.0)), 0.05)
	var score: float = dmg * rate + knock_mag * 0.25
	score *= context_mult(str(roll.get("slot", "")), context)
	if not is_finite_number(score):
		return 0.0
	return score


static func max_win_rate_bar() -> float:
	return float(_dict(data().get("dominance", {})).get("max_win_rate", 0.55))


static func require_distinct_winners() -> int:
	return int(_dict(data().get("dominance", {})).get("require_distinct_winners", 2))


static func require_distinct_contexts() -> int:
	return int(_dict(data().get("dominance", {})).get("require_distinct_contexts", 3))


static func dominance_violates(win_rate: float, distinct_winners: int, distinct_contexts: int) -> bool:
	return (
		win_rate >= max_win_rate_bar()
		or distinct_winners < require_distinct_winners()
		or distinct_contexts < require_distinct_contexts()
	)


static func overcap_weapon_id() -> String:
	return str(_dict(data().get("overcap", {})).get("weapon_id", "overcap_rifle"))


static func run_seeded_batch(seed_v: int, count: int = -1) -> Dictionary:
	if count < 0:
		count = scenario_count()
	var contexts: PackedStringArray = PackedStringArray([
		"close_melee", "high_ground", "pit", "grenade_chain", "friendly_fire"
	])
	var weapons: PackedStringArray = _Roster.ids()
	if weapons.is_empty():
		weapons = PackedStringArray(["fists", "pistol", "grenade"])
	var damages: PackedFloat32Array = PackedFloat32Array()
	var per_weapon: Dictionary = {}
	var context_best: Dictionary = {}
	var win_counts: Dictionary = {}
	var nan_count: int = 0
	var inf_count: int = 0
	var i: int = 0
	while i < weapons.size():
		var wid: String = String(weapons[i])
		per_weapon[wid] = {"n": 0, "sum": 0.0, "max": 0.0}
		win_counts[wid] = 0
		i += 1
	var c: int = 0
	while c < contexts.size():
		var ctx: String = String(contexts[c])
		var ctx_sum: Dictionary = {}
		var w0: int = 0
		while w0 < weapons.size():
			ctx_sum[String(weapons[w0])] = 0.0
			w0 += 1
		var per_ctx: int = count / contexts.size()
		if per_ctx < 1:
			per_ctx = count
		var n: int = 0
		while n < per_ctx:
			var best_id: String = ""
			var best_score: float = -1.0
			var w: int = 0
			while w < weapons.size():
				var wid2: String = String(weapons[w])
				var rng: RandomNumberGenerator = make_stream(seed_v, c * 100003 + n * 97 + w * 13)
				var roll: Dictionary = roll_weapon(rng, wid2, true)
				if not bool(roll.get("finite", false)):
					nan_count += 1
				var dmg: float = float(roll.get("damage", 0.0))
				if not is_finite_number(dmg):
					inf_count += 1
					dmg = 0.0
				damages.append(dmg)
				var sc: float = score_roll(wid2, ctx, roll)
				ctx_sum[wid2] = float(ctx_sum.get(wid2, 0.0)) + sc
				var row: Dictionary = per_weapon.get(wid2, {}) as Dictionary
				row["n"] = int(row.get("n", 0)) + 1
				row["sum"] = float(row.get("sum", 0.0)) + dmg
				row["max"] = maxf(float(row.get("max", 0.0)), dmg)
				per_weapon[wid2] = row
				if sc > best_score:
					best_score = sc
					best_id = wid2
				w += 1
			if best_id != "":
				win_counts[best_id] = int(win_counts.get(best_id, 0)) + 1
			n += 1
		var top: String = ""
		var top_v: float = -1.0
		var w1: int = 0
		while w1 < weapons.size():
			var id2: String = String(weapons[w1])
			var mean: float = float(ctx_sum.get(id2, 0.0)) / float(maxi(per_ctx, 1))
			if mean > top_v:
				top_v = mean
				top = id2
			w1 += 1
		context_best[ctx] = top
		c += 1
	var total_duels: int = 0
	var max_wins: int = 0
	var always: String = ""
	var k: int = 0
	while k < weapons.size():
		var id3: String = String(weapons[k])
		var wins: int = int(win_counts.get(id3, 0))
		total_duels += wins
		if wins > max_wins:
			max_wins = wins
			always = id3
		k += 1
	var win_rate: float = 0.0
	if total_duels > 0:
		win_rate = float(max_wins) / float(total_duels)
	var distinct_wins: int = 0
	var dw: int = 0
	while dw < weapons.size():
		if int(win_counts.get(String(weapons[dw]), 0)) > 0:
			distinct_wins += 1
		dw += 1
	var distinct_contexts: int = 0
	var seen_ctx: Dictionary = {}
	var ck: int = 0
	var ctx_keys: Array = context_best.keys()
	while ck < ctx_keys.size():
		var best_ctx: String = str(context_best.get(ctx_keys[ck], ""))
		if best_ctx != "" and not seen_ctx.has(best_ctx):
			seen_ctx[best_ctx] = true
			distinct_contexts += 1
		ck += 1
	var dominates: bool = dominance_violates(win_rate, distinct_wins, distinct_contexts)
	var stats: Dictionary = _damage_stats(damages)
	return {
		"count": count,
		"nan": nan_count,
		"inf": inf_count,
		"finite": nan_count == 0 and inf_count == 0,
		"stats": stats,
		"per_weapon": per_weapon,
		"context_best": context_best,
		"win_counts": win_counts,
		"win_rate_max": win_rate,
		"win_leader": always,
		"dominates": dominates,
		"distinct_winners": distinct_wins,
		"distinct_contexts": distinct_contexts,
		"method": "formula_rolls",
		"hardcoded_winners": false,
		"seed": seed_v,
	}


static func fixtures() -> Dictionary:
	return _dict(data().get("fixtures", {}))


static func fixture_names() -> Dictionary:
	return _dict(data().get("fixture_names", {}))


static func has_fixture(map_id: String) -> bool:
	return fixtures().has(map_id)


static func _base_weapon(weapon_id: String) -> Dictionary:
	var row: Dictionary = _Roster.item(weapon_id)
	var slot: String = str(row.get("slot", ""))
	var dmg: float = float(row.get("damage", 0.0))
	var knock: Vector2 = Vector2(80.0, -40.0)
	var rate: float = 1.0
	var spread: float = float(row.get("spread", 0.0))
	if slot == "melee" or weapon_id == "fists" or weapon_id == "kick":
		var style: String = "kick" if weapon_id == "kick" else "melee"
		dmg = _Combat.damage_of(weapon_id, style)
		knock = _Combat.knock_of(style, 1.0)
		var ticks: int = _Combat.total_ticks(weapon_id, style)
		rate = 60.0 / float(maxi(ticks, 1))
	elif slot == "firearm" or str(row.get("kind", "")) == "gun":
		dmg = _Aim.damage(weapon_id) * float(_Aim.pellets(weapon_id))
		spread = _Aim.spread(weapon_id)
		var cad: int = _Aim.cadence_ticks(weapon_id)
		rate = 60.0 / float(maxi(cad, 1))
		knock = Vector2(70.0, -30.0)
	elif slot == "explosive" or slot == "power" or str(row.get("kind", "")) == "throw":
		if weapon_id == "cinder":
			dmg = float(_dict(_Expl.data().get("cinder", {})).get("damage", 22.0))
			knock = Vector2(110.0, -60.0)
		else:
			dmg = _Expl.damage()
			knock = Vector2(_Expl.nade().get("knock", 140.0), _Expl.nade().get("knock_y", -80.0))
		rate = 60.0 / float(maxi(_Expl.fuse_ticks(), 1))
	return {
		"damage": dmg,
		"knock": knock,
		"rate": rate,
		"spread": spread,
		"slot": slot,
	}


static func _clamp_knock(knock: Vector2) -> Vector2:
	if not is_finite_number(knock.x) or not is_finite_number(knock.y):
		return Vector2.ZERO
	var mag: float = knock.length()
	var cap: float = knock_cap()
	if mag > cap and mag > 0.0:
		return knock * (cap / mag)
	return knock


static func _damage_stats(values: PackedFloat32Array) -> Dictionary:
	var n: int = values.size()
	if n == 0:
		return {"n": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0}
	var arr: Array = []
	var sum: float = 0.0
	var mn: float = values[0]
	var mx: float = values[0]
	var i: int = 0
	while i < n:
		var v: float = float(values[i])
		arr.append(v)
		sum += v
		if v < mn:
			mn = v
		if v > mx:
			mx = v
		i += 1
	arr.sort()
	return {
		"n": n,
		"min": mn,
		"max": mx,
		"mean": sum / float(n),
		"p50": float(arr[int(floor(float(n) * 0.50))]),
		"p95": float(arr[mini(n - 1, int(floor(float(n) * 0.95)))]),
	}


static func _fixture_has_no_one_way(fid: String, rows: Variant) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if fid == "fx_balance_chain" and rows is Array:
		var arr: Array = rows as Array
		var i: int = 0
		while i < arr.size():
			if str(arr[i]).contains("="):
				errors.append("chain fixture must not use = platforms")
			i += 1
	return errors


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1
