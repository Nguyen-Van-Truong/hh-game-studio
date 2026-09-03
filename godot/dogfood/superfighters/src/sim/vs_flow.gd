class_name VsFlow
extends RefCounted

const PATH := "res://data/sim/vs_flow.json"

static var _cache: Dictionary = {}


static func payload() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func validate() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var row: Dictionary = payload()
	if str(row.get("schema", "")) != "vf.sim.vs_flow.v1":
		errors.append("vs_flow schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("vs_flow title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("vs_flow must not claim Y8 parity")
	if bool(row.get("survival_shipped", true)):
		errors.append("vs_flow must not start Survival as a VS path")
	if not bool(row.get("title_survival_shipped", false)):
		errors.append("vs_flow catalog must acknowledge Title Survival is shipped")
	if bool(row.get("survival_as_stage", true)):
		errors.append("vs_flow must keep Survival as a separate Title mode")
	if bool(row.get("stage_lifecycle_shipped", true)):
		errors.append("vs_flow must not claim Stage lifecycle")
	var first: Dictionary = row.get("first_run", {}) as Dictionary
	var rematch: Dictionary = row.get("rematch", {}) as Dictionary
	if int(first.get("max_actions", 99)) > 3:
		errors.append("first_run max_actions must be <= 3")
	if int(first.get("max_seconds", 99)) > 30:
		errors.append("first_run max_seconds must be <= 30")
	if int(rematch.get("max_actions", 99)) > 2:
		errors.append("rematch max_actions must be <= 2")
	if int(rematch.get("max_seconds", 99)) > 5:
		errors.append("rematch max_seconds must be <= 5")
	if int(row.get("input_feedback_frames", 99)) != 2:
		errors.append("input_feedback_frames must be 2")
	if not bool(row.get("p1_p2_isolated", false)):
		errors.append("p1_p2_isolated must be true")
	return errors
