class_name HHAgentAnimationAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")
const _CodecScript: GDScript = preload("res://addons/hh_agent/core/hh_variant_codec.gd")

## Typed Godot 4.7.1 SpriteFrames / AnimationPlayer / AnimationTree verbs.
## Preview uses AnimationPlayer.play + current_animation / is_playing /
## current_animation_position. Headless editor play() may not keep is_playing;
## assigned current_animation + length is the honest Alternative.
## One EditorUndoRedoManager action per key/track/frames stroke. Agent: prefix.
## Catalog: register in actions.json. Generated plugin-validator.json /
## mcp-tools.json are coordinator-owned (`npm run generate`).

const METHOD_PLAY: String = "play"
const METHOD_STOP: String = "stop"
const TRACK_VALUE: String = "value"
const TRACK_METHOD: String = "method"
const TRACK_AUDIO: String = "audio"
const TRACK_BEZIER: String = "bezier"
const KEY_PAGE: int = 8

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()
var _codec: HHAgentVariantCodec = HHAgentVariantCodec.new()


class KeyStroke:
	extends RefCounted
	var animation: Animation
	var track: int = 0
	var times: PackedFloat32Array = PackedFloat32Array()
	var values: Array = []
	var undo_existed: PackedByteArray = PackedByteArray()
	var undo_values: Array = []

	func add(time: float, value: Variant, existed: bool, old_v: Variant) -> void:
		times.append(time)
		values.append(value)
		undo_existed.append(1 if existed else 0)
		undo_values.append(old_v)

	func apply() -> void:
		if animation == null:
			return
		var i: int = 0
		while i < times.size():
			var found: int = animation.track_find_key(track, times[i], Animation.FIND_MODE_EXACT)
			if found >= 0:
				animation.track_set_key_value(track, found, values[i])
			else:
				animation.track_insert_key(track, times[i], values[i])
			i += 1

	func revert() -> void:
		if animation == null:
			return
		var i: int = 0
		while i < times.size():
			if undo_existed[i] == 1:
				var found: int = animation.track_find_key(track, times[i], Animation.FIND_MODE_EXACT)
				if found >= 0:
					animation.track_set_key_value(track, found, undo_values[i])
			else:
				animation.track_remove_key_at_time(track, times[i])
			i += 1


class TrackStroke:
	extends RefCounted
	var animation: Animation
	var type: int = Animation.TYPE_VALUE
	var path: NodePath = NodePath()
	var idx: int = -1

	func apply() -> void:
		if animation == null:
			return
		idx = animation.add_track(type)
		animation.track_set_path(idx, path)

	func revert() -> void:
		if animation == null or idx < 0:
			return
		if idx < animation.get_track_count():
			animation.remove_track(idx)


class FramesStroke:
	extends RefCounted
	var frames: SpriteFrames
	var anim: String = ""
	var created_anim: bool = false
	var textures: Array[Texture2D] = []
	var durations: PackedFloat32Array = PackedFloat32Array()
	var old_speed: float = 5.0
	var new_speed: float = 5.0
	var old_loop: bool = true
	var new_loop: bool = true
	var speed_set: bool = false
	var loop_set: bool = false

	func apply() -> void:
		if frames == null:
			return
		if created_anim and not frames.has_animation(anim):
			frames.add_animation(anim)
		var i: int = 0
		while i < textures.size():
			frames.add_frame(anim, textures[i], durations[i])
			i += 1
		if speed_set:
			frames.set_animation_speed(anim, new_speed)
		if loop_set:
			frames.set_animation_loop(anim, new_loop)

	func revert() -> void:
		if frames == null:
			return
		if created_anim:
			if frames.has_animation(anim):
				frames.remove_animation(anim)
			return
		var i: int = textures.size() - 1
		while i >= 0:
			if frames.has_animation(anim) and frames.get_frame_count(anim) > 0:
				frames.remove_frame(anim, frames.get_frame_count(anim) - 1)
			i -= 1
		if frames.has_animation(anim):
			if speed_set:
				frames.set_animation_speed(anim, old_speed)
			if loop_set:
				frames.set_animation_loop(anim, old_loop)


func handles(action: String) -> bool:
	return (
		action == "library"
		or action == "animation"
		or action == "track"
		or action == "key"
		or action == "sprite_frames"
		or action == "state_machine"
		or action == "preview"
	)


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.animation" or not handles(action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not an animation verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "library":
		return _library(command_id, params, precondition, post)
	if action == "animation":
		return _animation(command_id, params, precondition, post)
	if action == "track":
		return _track(command_id, params, precondition, post)
	if action == "key":
		return _key(command_id, params, precondition, post)
	if action == "sprite_frames":
		return _sprite_frames(command_id, params, precondition, post)
	if action == "state_machine":
		return _state_machine(command_id, params, precondition, post)
	if action == "preview":
		return _preview(command_id, params, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "animation.%s is not a proven verb" % action, "")


func _fallback_post(action: String) -> String:
	if action == "library":
		return "animation_library_present"
	if action == "animation":
		return "animation_named_exists"
	if action == "track":
		return "animation_track_present"
	if action == "key":
		return "animation_key_at_time"
	if action == "sprite_frames":
		return "sprite_frames_animation_present"
	if action == "state_machine":
		return "state_machine_transition_present"
	if action == "preview":
		return "animation_preview_playing"
	return "animation_verb"


func _library(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_player(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var player: AnimationPlayer = hold.get("player") as AnimationPlayer
	var lib_name: String = str(params.get("library", ""))
	if lib_name.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "library name required", "params.library")
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var action_name: String = "%sanimation.library %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, lib_name]
	var existed: bool = player.has_animation_library(lib_name)
	var lib: AnimationLibrary = null
	if existed:
		lib = player.get_animation_library(lib_name)
	else:
		lib = AnimationLibrary.new()
		mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
		mgr.add_do_method(player, "add_animation_library", lib_name, lib)
		mgr.add_undo_method(player, "remove_animation_library", lib_name)
		mgr.commit_action()
	if not player.has_animation_library(lib_name):
		return _unverified(command_id, "add_animation_library readback missing")
	lib = player.get_animation_library(lib_name)
	if existed:
		mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
		mgr.add_do_method(player, "has_animation_library", lib_name)
		mgr.add_undo_method(player, "has_animation_library", lib_name)
		mgr.commit_action()
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	var library_path: String = str(params.get("library_path", ""))
	if not library_path.is_empty():
		persisted = _persist_res(command_id, lib, library_path)
		if persisted.get("ok", false) != true:
			return persisted
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _scene_after(edited, params)
	after["library"] = lib_name
	after["has_library"] = true
	after["animation_count"] = lib.get_animation_list().size()
	after["class_name"] = "AnimationLibrary"
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, not existed, action_name)


func _animation(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_library(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var lib: AnimationLibrary = hold.get("library") as AnimationLibrary
	var lib_name: String = str(hold.get("library_name", ""))
	var clip: String = str(params.get("name", ""))
	if clip.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "animation name required", "params.name")
	var length_sec: float = float(params.get("length_sec", 0.0))
	if length_sec < 0.01:
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "length_sec out of range", "params.length_sec")
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var action_name: String = "%sanimation.animation %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, clip]
	var existed: bool = lib.has_animation(clip)
	var anim: Animation = null
	var loop_on: bool = params.get("loop", false) == true
	if existed:
		anim = lib.get_animation(clip)
		var old_len: float = anim.length
		var old_loop: int = anim.loop_mode
		var new_loop: int = Animation.LOOP_LINEAR if loop_on else old_loop
		if params.has("loop"):
			new_loop = Animation.LOOP_LINEAR if loop_on else Animation.LOOP_NONE
		mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
		mgr.add_do_property(anim, "length", length_sec)
		mgr.add_undo_property(anim, "length", old_len)
		mgr.add_do_property(anim, "loop_mode", new_loop)
		mgr.add_undo_property(anim, "loop_mode", old_loop)
		mgr.commit_action()
	else:
		anim = Animation.new()
		anim.length = length_sec
		if params.has("loop"):
			anim.loop_mode = Animation.LOOP_LINEAR if loop_on else Animation.LOOP_NONE
		mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
		mgr.add_do_method(lib, "add_animation", clip, anim)
		mgr.add_undo_method(lib, "remove_animation", clip)
		mgr.commit_action()
	if not lib.has_animation(clip):
		return _unverified(command_id, "AnimationLibrary.add_animation readback missing")
	anim = lib.get_animation(clip)
	if not is_equal_approx(anim.length, length_sec):
		return _unverified(command_id, "animation length readback mismatch")
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _scene_after(edited, params)
	after["name"] = clip
	after["animation"] = clip
	after["library"] = lib_name
	after["length_sec"] = anim.length
	after["has_animation"] = true
	after["track_count"] = anim.get_track_count()
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _track(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_clip(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var player: AnimationPlayer = hold.get("player") as AnimationPlayer
	var anim: Animation = hold.get("animation") as Animation
	var clip: String = str(hold.get("clip", ""))
	var track_path: String = str(params.get("track_path", ""))
	if track_path.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "track_path required", "params.track_path")
	var type_s: String = str(params.get("track_type", ""))
	if type_s.is_empty():
		type_s = TRACK_VALUE
	var type_id: int = _track_type_id(type_s)
	if type_id < 0:
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "unknown animation track type", "params.track_type")
	var parsed: Dictionary = _parse_track_path(track_path)
	var node_part: String = str(parsed.get("node", ""))
	var prop_part: String = str(parsed.get("property", ""))
	if type_id == Animation.TYPE_VALUE and prop_part.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "value track requires Node:property", "params.track_path")
	var target: Node = _resolve_track_target(player, node_part)
	if target == null:
		return _unverified(command_id, "track path node not found")
	if type_id == Animation.TYPE_VALUE:
		var info: Dictionary = _prop_info(target, prop_part)
		if info.is_empty():
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "track property missing on node", "params.track_path")
	if type_id == Animation.TYPE_METHOD:
		if not (target is AnimationPlayer) and not (target is AnimatedSprite2D):
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "method track host must be AnimationPlayer or AnimatedSprite2D", "params.track_path")
	var existing: int = _find_track(anim, track_path, type_id)
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var action_name: String = "%sanimation.track %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, clip]
	var idx: int = existing
	var changed: bool = false
	if existing >= 0:
		mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
		mgr.add_do_method(anim, "track_set_path", existing, NodePath(track_path))
		mgr.add_undo_method(anim, "track_set_path", existing, anim.track_get_path(existing))
		mgr.commit_action()
	else:
		var stroke: TrackStroke = TrackStroke.new()
		stroke.animation = anim
		stroke.type = type_id
		stroke.path = NodePath(track_path)
		mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
		mgr.add_do_method(stroke, "apply")
		mgr.add_undo_method(stroke, "revert")
		mgr.add_do_reference(stroke)
		mgr.commit_action()
		idx = stroke.idx
		changed = true
	if idx < 0 or idx >= anim.get_track_count():
		return _unverified(command_id, "add_track readback missing")
	if str(anim.track_get_path(idx)) != track_path and not str(anim.track_get_path(idx)).ends_with(track_path):
		return _unverified(command_id, "track_set_path readback mismatch")
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _scene_after(edited, params)
	after["animation"] = clip
	after["track"] = idx
	after["track_path"] = track_path
	after["track_type"] = type_s
	after["target_path"] = node_part
	after["key_count"] = anim.track_get_key_count(idx)
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, changed, action_name)


func _key(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_clip(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var player: AnimationPlayer = hold.get("player") as AnimationPlayer
	var anim: Animation = hold.get("animation") as Animation
	var clip: String = str(hold.get("clip", ""))
	var track: int = int(params.get("track", -2))
	if track < 0 or track >= anim.get_track_count():
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "track index out of range", "params.track")
	var planned: Array[Dictionary] = []
	var raw_keys: Variant = params.get("keys", [])
	if typeof(raw_keys) == TYPE_ARRAY and (raw_keys as Array).size() > 0:
		for item_v: Variant in raw_keys:
			if typeof(item_v) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "key batch item must be an object", "params.keys")
			planned.append(item_v as Dictionary)
	else:
		planned.append(params)
	if planned.size() > 256:
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "key batch exceeds 256", "params.keys")
	var type_id: int = anim.track_get_type(track)
	if not _track_type_allowed(type_id):
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "unknown animation track type", "params.track")
	var path_s: String = str(anim.track_get_path(track))
	var parsed: Dictionary = _parse_track_path(path_s)
	var target: Node = _resolve_track_target(player, str(parsed.get("node", "")))
	var stroke: KeyStroke = KeyStroke.new()
	stroke.animation = anim
	stroke.track = track
	for item: Dictionary in planned:
		var time_sec: float = float(item.get("time_sec", -1.0))
		if time_sec < 0.0 or time_sec > anim.length + 0.0001:
			return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "key time outside animation length", "params.time_sec")
		var decoded: Dictionary = _decode_key_value(command_id, item.get("value"), type_id, target, str(parsed.get("property", "")))
		if decoded.get("ok", false) != true:
			return decoded
		var value_v: Variant = decoded.get("value")
		var found: int = anim.track_find_key(track, time_sec, Animation.FIND_MODE_EXACT)
		var old_v: Variant = null
		if found >= 0:
			old_v = anim.track_get_key_value(track, found)
		stroke.add(time_sec, value_v, found >= 0, old_v)
	var action_name: String = "%sanimation.key" % HHAgentConstants.UNDO_ACTION_PREFIX
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(stroke, "apply")
	mgr.add_undo_method(stroke, "revert")
	mgr.add_do_reference(stroke)
	mgr.commit_action()
	var i: int = 0
	while i < stroke.times.size():
		var found_after: int = anim.track_find_key(track, stroke.times[i], Animation.FIND_MODE_EXACT)
		if found_after < 0:
			return _unverified(command_id, "track_insert_key readback missing at %s" % str(stroke.times[i]))
		var got_v: Variant = anim.track_get_key_value(track, found_after)
		if not _values_close(got_v, stroke.values[i]):
			return _unverified(command_id, "track_get_key_value mismatch at %s" % str(stroke.times[i]))
		i += 1
	_meta.mark_dirty(str(params.get("scene", "")))
	var compact: Dictionary = _compact_keys(anim, track)
	var after: Dictionary = _scene_after(edited, params)
	after["animation"] = clip
	after["track"] = track
	after["time_sec"] = float(params.get("time_sec", stroke.times[0] if stroke.times.size() > 0 else 0.0))
	after["key_count"] = int(compact.get("key_count", 0))
	after["compact"] = compact.get("compact", false) == true
	after["readback_equals"] = true
	after["target_path"] = str(parsed.get("node", ""))
	after["source"] = "editor"
	if compact.get("compact", false) == true:
		after["samples"] = compact.get("samples", [])
	else:
		after["keys"] = compact.get("keys", [])
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _sprite_frames(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null or not (node is AnimatedSprite2D):
		return _unverified(command_id, "AnimatedSprite2D not found")
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var sprite: AnimatedSprite2D = node as AnimatedSprite2D
	var clip: String = str(params.get("animation", ""))
	if clip.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "animation name required", "params.animation")
	var frames_path: String = str(params.get("path", ""))
	var loaded: Dictionary = _ensure_frames(command_id, sprite, frames_path)
	if loaded.get("ok", false) != true:
		return loaded
	var frames: SpriteFrames = loaded.get("frames") as SpriteFrames
	var planned: Array[Dictionary] = []
	var raw_frames: Variant = params.get("frames", [])
	if typeof(raw_frames) == TYPE_ARRAY and (raw_frames as Array).size() > 0:
		for item_v: Variant in raw_frames:
			if typeof(item_v) != TYPE_DICTIONARY:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "frames item must be an object", "params.frames")
			planned.append(item_v as Dictionary)
	elif params.has("texture") or str(params.get("op", "")) == "add_frame":
		planned.append(params)
	var stroke: FramesStroke = FramesStroke.new()
	stroke.frames = frames
	stroke.anim = clip
	stroke.created_anim = not frames.has_animation(clip)
	if frames.has_animation(clip):
		stroke.old_speed = frames.get_animation_speed(clip)
		stroke.old_loop = frames.get_animation_loop(clip)
	if params.has("speed"):
		stroke.speed_set = true
		stroke.new_speed = float(params.get("speed", 5.0))
	if params.has("loop"):
		stroke.loop_set = true
		stroke.new_loop = params.get("loop", true) == true
	for item: Dictionary in planned:
		var tex_path: String = str(item.get("texture", ""))
		var tex: Texture2D = null
		if tex_path.is_empty():
			var placeholder: PlaceholderTexture2D = PlaceholderTexture2D.new()
			placeholder.size = Vector2(16, 16)
			tex = placeholder
		else:
			var jail: Dictionary = _meta.jail(command_id, tex_path)
			if jail.get("ok", false) != true:
				return jail
			var res: Resource = _load_res(tex_path)
			if res == null or not (res is Texture2D):
				return _unverified(command_id, "texture is not a Texture2D")
			tex = res as Texture2D
		stroke.textures.append(tex)
		stroke.durations.append(float(item.get("duration", 1.0)))
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var action_name: String = "%sanimation.sprite_frames %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, clip]
	var old_frames: SpriteFrames = sprite.sprite_frames
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(stroke, "apply")
	mgr.add_undo_method(stroke, "revert")
	if old_frames != frames:
		mgr.add_do_property(sprite, "sprite_frames", frames)
		mgr.add_undo_property(sprite, "sprite_frames", old_frames)
	var old_clip: StringName = sprite.animation
	if str(old_clip).is_empty() or not frames.has_animation(str(old_clip)):
		mgr.add_do_property(sprite, "animation", StringName(clip))
		mgr.add_undo_property(sprite, "animation", old_clip)
	mgr.add_do_reference(stroke)
	mgr.commit_action()
	if not frames.has_animation(clip):
		return _unverified(command_id, "SpriteFrames.add_animation readback missing")
	if sprite.sprite_frames != frames:
		return _unverified(command_id, "AnimatedSprite2D.sprite_frames readback mismatch")
	var frame_count: int = frames.get_frame_count(clip)
	if planned.size() > 0 and frame_count < planned.size():
		return _unverified(command_id, "SpriteFrames.add_frame readback count mismatch")
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	if not frames_path.is_empty():
		persisted = _persist_res(command_id, frames, frames_path)
		if persisted.get("ok", false) != true:
			return persisted
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _scene_after(edited, params)
	after["animation"] = clip
	after["has_animation"] = true
	after["frame_count"] = frame_count
	after["speed"] = frames.get_animation_speed(clip)
	after["loop"] = frames.get_animation_loop(clip)
	after["class_name"] = "SpriteFrames"
	after["target_path"] = str(params.get("node_path", ""))
	after["path"] = frames_path
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _state_machine(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null or not (node is AnimationTree):
		return _unverified(command_id, "AnimationTree not found")
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var tree: AnimationTree = node as AnimationTree
	var from_s: String = str(params.get("from", ""))
	var to_s: String = str(params.get("to", ""))
	if from_s.is_empty() or to_s.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "from/to required", "params.from")
	if to_s == "Start" or to_s == "End":
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "cannot target reserved Start/End as to", "params.to")
	if from_s == "End":
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "cannot use reserved End as from", "params.from")
	var switch_s: String = str(params.get("switch_mode", ""))
	if switch_s.is_empty():
		switch_s = "immediate"
	var switch_id: int = _switch_mode_id(switch_s)
	if switch_id < 0:
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "unknown switch_mode", "params.switch_mode")
	var condition: String = str(params.get("condition", ""))
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	var action_name: String = "%sanimation.state_machine %s-%s" % [HHAgentConstants.UNDO_ACTION_PREFIX, from_s, to_s]
	var old_root: AnimationRootNode = tree.tree_root
	var sm: AnimationNodeStateMachine = null
	if old_root is AnimationNodeStateMachine:
		sm = old_root as AnimationNodeStateMachine
	else:
		sm = AnimationNodeStateMachine.new()
	var player: AnimationPlayer = _find_player(edited, str(params.get("anim_player", "")), tree)
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	if tree.tree_root != sm:
		mgr.add_do_property(tree, "tree_root", sm)
		mgr.add_undo_property(tree, "tree_root", old_root)
	if player != null:
		var want_path: NodePath = tree.get_path_to(player)
		if tree.anim_player != want_path:
			mgr.add_do_property(tree, "anim_player", want_path)
			mgr.add_undo_property(tree, "anim_player", tree.anim_player)
	var from_node: AnimationNodeAnimation = null
	var to_node: AnimationNodeAnimation = null
	if from_s == "Start" or from_s == "End":
		pass
	elif not sm.has_node(from_s):
		from_node = AnimationNodeAnimation.new()
		from_node.animation = _clip_for_tree(player, from_s)
		mgr.add_do_method(sm, "add_node", from_s, from_node, Vector2(0, 0))
		mgr.add_undo_method(sm, "remove_node", from_s)
	if not sm.has_node(to_s):
		to_node = AnimationNodeAnimation.new()
		to_node.animation = _clip_for_tree(player, to_s)
		mgr.add_do_method(sm, "add_node", to_s, to_node, Vector2(200, 0))
		mgr.add_undo_method(sm, "remove_node", to_s)
	if sm.has_node("Start") and not sm.has_transition("Start", from_s):
		var start_trans: AnimationNodeStateMachineTransition = AnimationNodeStateMachineTransition.new()
		start_trans.advance_mode = AnimationNodeStateMachineTransition.ADVANCE_MODE_AUTO
		mgr.add_do_method(sm, "add_transition", "Start", from_s, start_trans)
		mgr.add_undo_method(sm, "remove_transition", "Start", from_s)
		mgr.add_do_reference(start_trans)
	var trans: AnimationNodeStateMachineTransition = null
	var added_trans: bool = false
	if str(params.get("op", "")) != "add_node" and not sm.has_transition(from_s, to_s):
		trans = AnimationNodeStateMachineTransition.new()
		trans.switch_mode = switch_id
		if not condition.is_empty():
			trans.advance_condition = StringName(condition)
			trans.advance_mode = AnimationNodeStateMachineTransition.ADVANCE_MODE_ENABLED
		else:
			trans.advance_mode = AnimationNodeStateMachineTransition.ADVANCE_MODE_AUTO
		mgr.add_do_method(sm, "add_transition", from_s, to_s, trans)
		mgr.add_undo_method(sm, "remove_transition", from_s, to_s)
		added_trans = true
	if from_node != null:
		mgr.add_do_reference(from_node)
	if to_node != null:
		mgr.add_do_reference(to_node)
	if trans != null:
		mgr.add_do_reference(trans)
	mgr.commit_action()
	if tree.tree_root != sm:
		return _unverified(command_id, "AnimationTree.tree_root readback mismatch")
	if not sm.has_node(from_s) or not sm.has_node(to_s):
		return _unverified(command_id, "AnimationNodeStateMachine.add_node readback missing")
	var has_trans: bool = sm.has_transition(from_s, to_s)
	if str(params.get("op", "")) != "add_node" and not has_trans:
		return _unverified(command_id, "add_transition readback missing")
	var got_condition: String = ""
	var got_switch: int = switch_id
	if has_trans:
		var live: AnimationNodeStateMachineTransition = _get_transition(sm, from_s, to_s)
		if live != null:
			got_condition = str(live.advance_condition)
			got_switch = live.switch_mode
			if not condition.is_empty() and got_condition != condition:
				return _unverified(command_id, "transition condition readback mismatch")
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _scene_after(edited, params)
	after["from"] = from_s
	after["to"] = to_s
	after["has_transition"] = has_trans
	after["has_node_from"] = sm.has_node(from_s)
	after["has_node_to"] = sm.has_node(to_s)
	after["condition"] = got_condition
	after["switch_mode"] = switch_s
	after["switch_mode_id"] = got_switch
	after["class_name"] = "AnimationNodeStateMachine"
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, added_trans or from_node != null or to_node != null, action_name)


func _preview(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), {})
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var player: AnimationPlayer = _as_player(edited, str(params.get("node_path", "")))
	if player == null:
		return _unverified(command_id, "AnimationPlayer not found for preview")
	var clip: String = str(params.get("animation", ""))
	var library: String = str(params.get("library", ""))
	var play_name: String = _resolve_play_name(player, clip, library)
	if play_name.is_empty() or not player.has_animation(play_name):
		return _unverified(command_id, "preview animation missing")
	var anim: Animation = player.get_animation(play_name)
	player.play(play_name)
	var current: String = str(player.current_animation)
	if current.is_empty():
		current = str(player.assigned_animation)
	var playing: bool = player.is_playing()
	var pos: float = player.current_animation_position
	var length: float = player.current_animation_length
	if length <= 0.0 and anim != null:
		length = anim.length
	if not _anim_name_matches(current, clip, library) and not _anim_name_matches(play_name, clip, library):
		return _unverified(command_id, "play() did not assign current_animation")
	if current.is_empty():
		return _unverified(command_id, "play() did not assign current_animation")
	var after: Dictionary = {
		"scene": str(params.get("scene", "")),
		"node_path": str(params.get("node_path", "")),
		"animation": clip,
		"play_name": play_name,
		"current_animation": current,
		"assigned_animation": str(player.assigned_animation),
		"current_animation_position": pos,
		"is_playing": playing,
		"length": length,
		"source": "editor",
	}
	if not playing:
		after["alternative"] = "headless editor play() may not keep is_playing; assigned current_animation + length"
		after["playing_alternative"] = true
	if params.get("include_keys", false) == true and anim != null:
		var keys_page: Dictionary = _page_animation_keys(anim, params)
		after["track_count"] = anim.get_track_count()
		after["key_count"] = int(keys_page.get("key_count", 0))
		after["compact"] = keys_page.get("compact", false) == true
		after["samples"] = keys_page.get("samples", [])
		if keys_page.has("keys"):
			after["keys"] = keys_page.get("keys", [])
		after["total"] = int(keys_page.get("total", 0))
		after["offset"] = int(keys_page.get("offset", 0))
		after["next_offset"] = int(keys_page.get("next_offset", -1))
		after["truncated"] = keys_page.get("truncated", false) == true
	elif anim != null:
		after["track_count"] = anim.get_track_count()
		after["key_count"] = _sum_keys(anim)
	return _errors.ok_read(command_id, _checks(post), after)


func _hold_player(command_id: String, params: Dictionary, precondition: Dictionary) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var player: AnimationPlayer = _as_player(edited, str(params.get("node_path", "")))
	if player == null:
		return _unverified(command_id, "AnimationPlayer not found")
	var packed_err: Dictionary = _reject_packed(command_id, player, edited)
	if not packed_err.is_empty():
		return packed_err
	return {"ok": true, "root": edited, "player": player}


func _hold_library(command_id: String, params: Dictionary, precondition: Dictionary) -> Dictionary:
	var hold: Dictionary = _hold_player(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var player: AnimationPlayer = hold.get("player") as AnimationPlayer
	var lib_name: String = str(params.get("library", ""))
	var lib: AnimationLibrary = _pick_library(player, lib_name)
	if lib == null:
		return _unverified(command_id, "animation library missing")
	if lib_name.is_empty():
		lib_name = _library_name_of(player, lib)
	hold["library"] = lib
	hold["library_name"] = lib_name
	return hold


func _hold_clip(command_id: String, params: Dictionary, precondition: Dictionary) -> Dictionary:
	var hold: Dictionary = _hold_library(command_id, params, precondition)
	if hold.get("ok", false) != true:
		return hold
	var player: AnimationPlayer = hold.get("player") as AnimationPlayer
	var lib: AnimationLibrary = hold.get("library") as AnimationLibrary
	var clip: String = str(params.get("animation", params.get("name", "")))
	if clip.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "animation name required", "params.animation")
	var anim: Animation = null
	if lib.has_animation(clip):
		anim = lib.get_animation(clip)
	else:
		var play_name: String = _resolve_play_name(player, clip, str(hold.get("library_name", "")))
		if player.has_animation(play_name):
			anim = player.get_animation(play_name)
	if anim == null:
		return _unverified(command_id, "named Animation missing")
	hold["animation"] = anim
	hold["clip"] = clip
	return hold


func _pick_library(player: AnimationPlayer, lib_name: String) -> AnimationLibrary:
	if not lib_name.is_empty() and player.has_animation_library(lib_name):
		return player.get_animation_library(lib_name)
	var names: Array = player.get_animation_library_list()
	if names.is_empty():
		return null
	if not lib_name.is_empty():
		return null
	return player.get_animation_library(names[0])


func _library_name_of(player: AnimationPlayer, lib: AnimationLibrary) -> String:
	var names: Array = player.get_animation_library_list()
	for name_v: Variant in names:
		var name_s: String = str(name_v)
		if player.get_animation_library(name_s) == lib:
			return name_s
	return ""


func _as_player(root: Node, path_s: String) -> AnimationPlayer:
	var node: Node = _resolve(root, path_s)
	if node is AnimationPlayer:
		return node as AnimationPlayer
	if node is AnimationTree:
		var tree: AnimationTree = node as AnimationTree
		var via: Node = tree.get_node_or_null(tree.anim_player)
		if via is AnimationPlayer:
			return via as AnimationPlayer
	return null


func _find_player(edited: Node, hint: String, tree: AnimationTree) -> AnimationPlayer:
	if not hint.is_empty():
		var hinted: Node = _resolve(edited, hint)
		if hinted is AnimationPlayer:
			return hinted as AnimationPlayer
	if tree != null and tree.anim_player != NodePath():
		var via: Node = tree.get_node_or_null(tree.anim_player)
		if via is AnimationPlayer:
			return via as AnimationPlayer
	return _first_player(edited)


func _first_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	var i: int = 0
	while i < node.get_child_count():
		var found: AnimationPlayer = _first_player(node.get_child(i))
		if found != null:
			return found
		i += 1
	return null


func _clip_for_tree(player: AnimationPlayer, clip: String) -> String:
	if player == null:
		return clip
	var play_name: String = _resolve_play_name(player, clip, "")
	if play_name.is_empty():
		return clip
	return play_name


func _resolve_play_name(player: AnimationPlayer, clip: String, library: String) -> String:
	if not library.is_empty():
		var qualified: String = "%s/%s" % [library, clip]
		if player.has_animation(qualified):
			return qualified
	if player.has_animation(clip):
		return clip
	var names: Array = player.get_animation_library_list()
	for name_v: Variant in names:
		var lib_name: String = str(name_v)
		var lib: AnimationLibrary = player.get_animation_library(lib_name)
		if lib != null and lib.has_animation(clip):
			if lib_name.is_empty():
				return clip
			return "%s/%s" % [lib_name, clip]
	return ""


func _anim_name_matches(got: String, want: String, library: String) -> bool:
	if got == want:
		return true
	if got.get_file() == want:
		return true
	if not library.is_empty() and got == "%s/%s" % [library, want]:
		return true
	return false


func _track_type_id(type_s: String) -> int:
	if type_s == TRACK_VALUE:
		return Animation.TYPE_VALUE
	if type_s == TRACK_METHOD:
		return Animation.TYPE_METHOD
	if type_s == TRACK_AUDIO:
		return Animation.TYPE_AUDIO
	if type_s == TRACK_BEZIER:
		return Animation.TYPE_BEZIER
	return -1


func _track_type_allowed(type_id: int) -> bool:
	return (
		type_id == Animation.TYPE_VALUE
		or type_id == Animation.TYPE_METHOD
		or type_id == Animation.TYPE_AUDIO
		or type_id == Animation.TYPE_BEZIER
	)


func _switch_mode_id(raw: String) -> int:
	if raw == "immediate":
		return AnimationNodeStateMachineTransition.SWITCH_MODE_IMMEDIATE
	if raw == "sync":
		return AnimationNodeStateMachineTransition.SWITCH_MODE_SYNC
	if raw == "at_end":
		return AnimationNodeStateMachineTransition.SWITCH_MODE_AT_END
	return -1


func _parse_track_path(track_path: String) -> Dictionary:
	var colon: int = track_path.find(":")
	if colon < 0:
		return {"node": track_path, "property": ""}
	return {
		"node": track_path.substr(0, colon),
		"property": track_path.substr(colon + 1),
	}


func _resolve_track_target(player: AnimationPlayer, node_part: String) -> Node:
	if player == null:
		return null
	var root: Node = player.get_node_or_null(player.root_node)
	if root == null:
		root = player.get_parent()
	if root == null:
		return null
	if node_part.is_empty() or node_part == ".":
		return root
	var found: Node = root.get_node_or_null(NodePath(node_part))
	if found != null:
		return found
	return player.get_node_or_null(NodePath(node_part))


func _find_track(anim: Animation, track_path: String, type_id: int) -> int:
	var i: int = 0
	while i < anim.get_track_count():
		if anim.track_get_type(i) == type_id and str(anim.track_get_path(i)) == track_path:
			return i
		i += 1
	return -1


func _prop_info(node: Node, prop: String) -> Dictionary:
	if node == null or prop.is_empty():
		return {}
	for item_v: Variant in node.get_property_list():
		if item_v is Dictionary and str((item_v as Dictionary).get("name", "")) == prop:
			return item_v
	return {}


func _decode_key_value(
	command_id: String,
	raw: Variant,
	type_id: int,
	target: Node,
	prop: String,
) -> Dictionary:
	if type_id == Animation.TYPE_METHOD:
		return _decode_method_key(command_id, raw, target)
	var decoded: Dictionary = _codec.decode(raw, "params.value")
	if decoded.get("ok", false) != true:
		return _fail_enc(command_id, decoded)
	var kind: String = str(decoded.get("type", ""))
	var value_v: Variant = decoded.get("value")
	if type_id == Animation.TYPE_BEZIER:
		if kind != "float" and kind != "int":
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "bezier key requires a number", "params.value")
		return {"ok": true, "value": float(value_v)}
	if type_id == Animation.TYPE_AUDIO:
		if value_v == null or not (value_v is Resource):
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "audio key requires a Resource", "params.value")
		return {"ok": true, "value": value_v}
	if type_id == Animation.TYPE_VALUE and target != null and not prop.is_empty():
		var info: Dictionary = _prop_info(target, prop)
		if not info.is_empty():
			var type_err: Dictionary = _codec.types_compatible(int(info.get("type", 0)), kind, value_v, str(info.get("class_name", "")))
			if not type_err.is_empty():
				return _fail_enc(command_id, type_err)
	return {"ok": true, "value": value_v}


func _decode_method_key(command_id: String, raw: Variant, target: Node) -> Dictionary:
	if target != null and not (target is AnimationPlayer) and not (target is AnimatedSprite2D):
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "method track host must be AnimationPlayer or AnimatedSprite2D", "params.track_path")
	var method_s: String = ""
	var args: Array = []
	if typeof(raw) == TYPE_DICTIONARY:
		var rec: Dictionary = raw
		if str(rec.get("schema", "")) == HHAgentVariantCodec.SCHEMA:
			var decoded: Dictionary = _codec.decode(raw, "params.value")
			if decoded.get("ok", false) != true:
				return _fail_enc(command_id, decoded)
			var kind: String = str(decoded.get("type", ""))
			if kind == "string":
				method_s = str(decoded.get("value", ""))
			elif kind == "Dictionary" and decoded.get("value") is Dictionary:
				var inner: Dictionary = decoded.get("value")
				method_s = str(inner.get("method", ""))
				var args_v: Variant = inner.get("args", [])
				if typeof(args_v) == TYPE_ARRAY:
					args = args_v
			else:
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "method key must name an allowlisted method", "params.value")
		else:
			method_s = str(rec.get("method", ""))
			var raw_args: Variant = rec.get("args", [])
			if typeof(raw_args) == TYPE_ARRAY:
				args = raw_args
	if not _method_allowed(method_s):
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "method name is not allowlisted", "params.value")
	return {"ok": true, "value": {"method": StringName(method_s), "args": args}}


func _method_allowed(method_s: String) -> bool:
	return method_s == METHOD_PLAY or method_s == METHOD_STOP


func _values_close(got: Variant, want: Variant) -> bool:
	if _codec.same(got, want):
		return true
	if typeof(got) == TYPE_DICTIONARY and typeof(want) == TYPE_DICTIONARY:
		var g: Dictionary = got
		var w: Dictionary = want
		return str(g.get("method", "")) == str(w.get("method", ""))
	if typeof(got) == TYPE_FLOAT or typeof(want) == TYPE_FLOAT:
		return is_equal_approx(float(got), float(want))
	return got == want


func _compact_keys(anim: Animation, track: int) -> Dictionary:
	var n: int = anim.track_get_key_count(track)
	if n <= KEY_PAGE:
		var keys: Array = []
		var i: int = 0
		while i < n:
			keys.append(_key_json(anim, track, i))
			i += 1
		return {"key_count": n, "compact": false, "keys": keys}
	var samples: Array = []
	samples.append(_key_json(anim, track, 0))
	samples.append(_key_json(anim, track, int(n / 2)))
	samples.append(_key_json(anim, track, n - 1))
	return {"key_count": n, "compact": true, "samples": samples}


func _page_animation_keys(anim: Animation, params: Dictionary) -> Dictionary:
	var flat: Array = []
	var t: int = 0
	while t < anim.get_track_count():
		var k: int = 0
		var kn: int = anim.track_get_key_count(t)
		while k < kn:
			var row: Dictionary = _key_json(anim, t, k)
			row["track"] = t
			flat.append(row)
			k += 1
		t += 1
	var total: int = flat.size()
	var offset: int = int(params.get("offset", 0))
	var limit: int = int(params.get("limit", 0))
	if offset < 0:
		offset = 0
	if limit <= 0:
		limit = HHAgentConstants.MAX_PAGE
	if limit > HHAgentConstants.MAX_PAGE:
		limit = HHAgentConstants.MAX_PAGE
	if offset == 0 and not params.has("offset") and not params.has("limit") and total > HHAgentConstants.MAX_PAGE:
		return {
			"key_count": total,
			"compact": true,
			"samples": _sample_flat(flat),
			"total": total,
			"offset": 0,
			"next_offset": -1,
			"truncated": true,
		}
	var page: Array = []
	var i: int = offset
	while i < total and page.size() < limit:
		page.append(flat[i])
		i += 1
	var next_offset: int = offset + page.size()
	return {
		"key_count": total,
		"compact": total > KEY_PAGE,
		"keys": page if total <= KEY_PAGE else [],
		"samples": page if total > KEY_PAGE else [],
		"total": total,
		"offset": offset,
		"next_offset": next_offset if next_offset < total else -1,
		"truncated": next_offset < total,
	}


func _sample_flat(flat: Array) -> Array:
	if flat.is_empty():
		return []
	var out: Array = [flat[0]]
	if flat.size() > 2:
		out.append(flat[int(flat.size() / 2)])
	if flat.size() > 1:
		out.append(flat[flat.size() - 1])
	return out


func _sum_keys(anim: Animation) -> int:
	var n: int = 0
	var i: int = 0
	while i < anim.get_track_count():
		n += anim.track_get_key_count(i)
		i += 1
	return n


func _key_json(anim: Animation, track: int, idx: int) -> Dictionary:
	var enc: Dictionary = _codec.encode(anim.track_get_key_value(track, idx))
	return {
		"track": track,
		"index": idx,
		"time_sec": anim.track_get_key_time(track, idx),
		"value": {"type": str(enc.get("type", "")), "ok": enc.get("ok", false) == true},
	}


func _get_transition(
	sm: AnimationNodeStateMachine,
	from_s: String,
	to_s: String,
) -> AnimationNodeStateMachineTransition:
	var i: int = 0
	while i < sm.get_transition_count():
		if str(sm.get_transition_from(i)) == from_s and str(sm.get_transition_to(i)) == to_s:
			return sm.get_transition(i)
		i += 1
	return null


func _ensure_frames(command_id: String, sprite: AnimatedSprite2D, frames_path: String) -> Dictionary:
	if not frames_path.is_empty():
		if FileAccess.file_exists(frames_path) or ResourceLoader.exists(frames_path):
			var jail: Dictionary = _meta.jail(command_id, frames_path)
			if jail.get("ok", false) != true:
				return jail
			var res: Resource = _load_res(frames_path)
			if res == null or not (res is SpriteFrames):
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "path is not a SpriteFrames", frames_path)
			return {"ok": true, "frames": res as SpriteFrames}
		var created_jail: Dictionary = _meta.jail(command_id, frames_path)
		if created_jail.get("ok", false) != true:
			return created_jail
		if not frames_path.ends_with(".tres") and not frames_path.ends_with(".res"):
			return _errors.fail(command_id, HHAgentErrors.E_PATH, "SpriteFrames persist requires .tres or .res", frames_path)
		return {"ok": true, "frames": SpriteFrames.new()}
	if sprite.sprite_frames != null:
		return {"ok": true, "frames": sprite.sprite_frames}
	return {"ok": true, "frames": SpriteFrames.new()}


func _persist_res(command_id: String, res: Resource, res_path: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not res_path.ends_with(".tres") and not res_path.ends_with(".res"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "resource persist requires .tres or .res", res_path)
	var dir_err: Error = _meta.ensure_parent_dir(res_path)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create resource directory", res_path)
	var save_err: Error = ResourceSaver.save(res, res_path)
	if save_err != OK:
		return _unverified(command_id, "ResourceSaver.save failed: %s" % error_string(save_err))
	_meta.refresh_fs(res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "resource file missing after save")
	var disk: String = _meta.disk_hash(res_path)
	if disk.is_empty() or disk == "missing":
		return _unverified(command_id, "resource disk hash missing after save")
	return {"ok": true, "disk_hash": disk, "path": res_path}


func _scene_after(edited: Node, params: Dictionary) -> Dictionary:
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	return after


func _hold_scene(command_id: String, res_path: String, precondition: Dictionary) -> Dictionary:
	var gated: Dictionary = _meta.jail(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	if not _meta.is_scene_path(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path must be .tscn or .scn", res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "scene missing")
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		EditorInterface.open_scene_from_path(res_path)
		edited = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		return _unverified(command_id, "edited_scene is not %s" % res_path)
	if not precondition.is_empty():
		var want_fp: String = str(precondition.get("fingerprint", ""))
		var want_hv: String = str(precondition.get("history_version", ""))
		var want_hash: String = str(precondition.get("scene_hash", ""))
		if not want_fp.is_empty() and want_fp != _meta.fingerprint(edited):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "editor fingerprint changed; resync", "precondition.fingerprint")
		if not want_hv.is_empty() and want_hv != str(_meta.history_version(edited)):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "editor history version changed; resync", "precondition.history_version")
		if not want_hash.is_empty() and want_hash != _meta.disk_hash(res_path):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "disk hash changed (human/external edit); resync", "precondition.scene_hash")
	return {"ok": true, "root": edited}


func _resolve(root: Node, path_s: String) -> Node:
	if root == null:
		return null
	if path_s.is_empty() or path_s == "." or path_s == root.name:
		return root
	var found: Node = root.get_node_or_null(NodePath(path_s))
	if found != null:
		return found
	if path_s.begins_with(root.name + "/"):
		return root.get_node_or_null(NodePath(path_s.substr(root.name.length() + 1)))
	return null


func _reject_packed(command_id: String, node: Node, edited: Node) -> Dictionary:
	if _identity.is_packed_internal(node, edited):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"packed instance child requires make_local; refusing a flatten",
			"params.node_path",
		)
	return {}


func _load_res(res_path: String) -> Resource:
	if res_path.is_empty():
		return null
	if ResourceLoader.exists(res_path):
		var loaded: Resource = ResourceLoader.load(res_path, "", ResourceLoader.CACHE_MODE_REUSE)
		if loaded != null:
			return loaded
	if FileAccess.file_exists(res_path):
		return ResourceLoader.load(res_path)
	return null


func _mgr() -> EditorUndoRedoManager:
	return EditorInterface.get_editor_undo_redo()


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _fail_enc(command_id: String, enc: Dictionary) -> Dictionary:
	var err_v: Variant = enc.get("error", {})
	if err_v is Dictionary:
		var err: Dictionary = err_v
		return _errors.fail(command_id, str(err.get("code", HHAgentErrors.E_INVALID_VARIANT)), str(err.get("message", "variant")), str(err.get("path", "")))
	return _unverified(command_id, "variant codec failed")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out
