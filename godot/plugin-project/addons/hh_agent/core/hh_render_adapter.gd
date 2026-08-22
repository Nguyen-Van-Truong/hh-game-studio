class_name HHAgentRenderAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")
const _CodecScript: GDScript = preload("res://addons/hh_agent/core/hh_variant_codec.gd")

## Typed Godot 4.7.1 shader / GPUParticles2D / 2D quality verbs.
## Shader diagnostic = get_mode + get_shader_uniform_list. Do not invent a compile API.
## Invalid shader (missing shader_type / mode mismatch / required uniform absent /
## garbage) is a typed fail. NEVER ok:true. Write .gdshader via A4 tmp+rename,
## not the script adapter. Particles use engine get_rect / visibility_rect AABB.
## Never invent a 32px box. Compatibility skips glow/volumetric honestly.
## Catalog: register in actions.json. Generated plugin-validator.json /
## mcp-tools.json are coordinator-owned (`npm run generate`).

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()
var _codec: HHAgentVariantCodec = HHAgentVariantCodec.new()


class MaterialStroke:
	extends RefCounted
	var item: CanvasItem
	var old_mat: Material
	var new_mat: Material

	func apply() -> void:
		if item == null:
			return
		item.material = new_mat

	func revert() -> void:
		if item == null:
			return
		item.material = old_mat


class ParticlesStroke:
	extends RefCounted
	var particles: GPUParticles2D
	var old_amount: int = 8
	var new_amount: int = 8
	var old_life: float = 1.0
	var new_life: float = 1.0
	var old_proc: Material
	var new_proc: Material
	var old_tex: Texture2D
	var new_tex: Texture2D
	var tex_set: bool = false

	func apply() -> void:
		if particles == null:
			return
		particles.amount = new_amount
		particles.lifetime = new_life
		particles.process_material = new_proc
		if tex_set:
			particles.texture = new_tex

	func revert() -> void:
		if particles == null:
			return
		particles.amount = old_amount
		particles.lifetime = old_life
		particles.process_material = old_proc
		if tex_set:
			particles.texture = old_tex


class QualityStroke:
	extends RefCounted
	var light: PointLight2D
	var env_node: WorldEnvironment
	var modulate: CanvasModulate
	var old_energy: float = 1.0
	var new_energy: float = 1.0
	var old_color: Color = Color.WHITE
	var new_color: Color = Color.WHITE
	var old_shadow: bool = false
	var new_shadow: bool = false
	var light_set: bool = false
	var old_mod: Color = Color.WHITE
	var new_mod: Color = Color.WHITE
	var mod_set: bool = false
	var old_env: Environment
	var new_env: Environment
	var env_set: bool = false

	func apply() -> void:
		if light_set and light != null:
			light.energy = new_energy
			light.color = new_color
			light.shadow_enabled = new_shadow
		if mod_set and modulate != null:
			modulate.color = new_mod
		if env_set and env_node != null:
			env_node.environment = new_env

	func revert() -> void:
		if light_set and light != null:
			light.energy = old_energy
			light.color = old_color
			light.shadow_enabled = old_shadow
		if mod_set and modulate != null:
			modulate.color = old_mod
		if env_set and env_node != null:
			env_node.environment = old_env


func handles(action: String) -> bool:
	return action == "shader" or action == "particles" or action == "quality"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.render" or not handles(action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a render verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "shader":
		return _shader(command_id, params, precondition, post)
	if action == "particles":
		return _particles(command_id, params, precondition, post)
	if action == "quality":
		return _quality(command_id, params, precondition, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "render.%s is not a proven verb" % action, "")


func _fallback_post(action: String) -> String:
	if action == "shader":
		return "render_shader_mode_uniforms_match"
	if action == "particles":
		return "render_particles_amount_lifetime_match"
	if action == "quality":
		return "render_quality_readback_matches"
	return "render_verb"


static func engine_world_rect(node: Node) -> Dictionary:
	if node == null:
		return _rect_fail()
	if node is GPUParticles2D:
		return _particles_world_rect(node as GPUParticles2D)
	if node is Sprite2D:
		var spr: Sprite2D = node as Sprite2D
		var local: Rect2 = spr.get_rect()
		if local.size.x > 0.0 and local.size.y > 0.0:
			return {
				"ok": true,
				"rect": spr.get_global_transform() * local,
				"rect_source": "get_rect",
				"invented_box": false,
				"used_engine_transform": true,
			}
	if node is PointLight2D:
		var light: PointLight2D = node as PointLight2D
		if light.texture != null:
			var sz: Vector2 = light.texture.get_size()
			if sz.x > 0.0 and sz.y > 0.0:
				var local_l: Rect2 = Rect2(-sz * 0.5, sz)
				return {
					"ok": true,
					"rect": light.get_global_transform() * local_l,
					"rect_source": "texture",
					"invented_box": false,
					"used_engine_transform": true,
				}
	if node is Control:
		var ctrl: Control = node as Control
		var gr: Rect2 = ctrl.get_global_rect()
		if gr.size.x > 0.0 and gr.size.y > 0.0:
			return {
				"ok": true,
				"rect": gr,
				"rect_source": "get_global_rect",
				"invented_box": false,
				"used_engine_transform": true,
			}
	return _rect_fail()


func _shader(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null or not (node is CanvasItem):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"render.shader requires a CanvasItem",
			"params.node_path",
		)
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var shader_path: String = str(params.get("shader", ""))
	var material_path: String = str(params.get("material", ""))
	if shader_path.contains("::") or material_path.contains("::"):
		return _unverified(command_id, "refusing RAM-only render durable ACK")
	if shader_path.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "shader path required", "params.shader")
	var code: String = str(params.get("code", ""))
	if code.is_empty() and (FileAccess.file_exists(shader_path) or ResourceLoader.exists(shader_path)):
		if shader_path.ends_with(".gdshader"):
			code = FileAccess.get_file_as_string(shader_path)
		else:
			var existing: Resource = _load_res(shader_path)
			if existing is Shader:
				code = (existing as Shader).code
	var required: String = str(params.get("required_uniform", ""))
	var diagnosed: Dictionary = _diagnose_shader(command_id, code, required)
	if diagnosed.get("ok", false) != true:
		return diagnosed
	var shader: Shader = diagnosed.get("shader") as Shader
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	if shader_path.ends_with(".gdshader"):
		persisted = _atomic_shader_text(command_id, shader_path, code)
		if persisted.get("ok", false) != true:
			return persisted
		var loaded: Resource = _load_res(shader_path)
		if loaded is Shader:
			var loaded_sh: Shader = loaded as Shader
			loaded_sh.code = code
			var again: Dictionary = _bind_shader_diag(command_id, loaded_sh, required)
			if again.get("ok", false) == true:
				shader = loaded_sh
				diagnosed = again
	elif _is_external_res(shader_path):
		shader.code = code
		persisted = _persist_res(command_id, shader, shader_path)
		if persisted.get("ok", false) != true:
			return persisted
	else:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "shader persist requires .gdshader or .tres", shader_path)
	var item: CanvasItem = node as CanvasItem
	var mat: ShaderMaterial = ShaderMaterial.new()
	if _is_external_res(material_path) and (FileAccess.file_exists(material_path) or ResourceLoader.exists(material_path)):
		var mat_res: Resource = _load_res(material_path)
		if mat_res is ShaderMaterial:
			mat = mat_res as ShaderMaterial
	mat.shader = shader
	var params_err: Dictionary = _apply_shader_params(command_id, mat, params)
	if params_err.get("ok", false) != true:
		return params_err
	var stroke: MaterialStroke = MaterialStroke.new()
	stroke.item = item
	stroke.old_mat = item.material
	stroke.new_mat = mat
	var action_name: String = "%srender.shader" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	if item.material != mat:
		return _unverified(command_id, "ShaderMaterial assign readback missing")
	if _is_external_res(material_path):
		var mat_saved: Dictionary = _persist_res(command_id, mat, material_path)
		if mat_saved.get("ok", false) != true:
			return mat_saved
		if str(persisted.get("disk_hash", "")).is_empty():
			persisted = mat_saved
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _render_after(edited, params, item)
	after["shader"] = shader_path
	after["mode"] = "MODE_CANVAS_ITEM"
	after["mode_id"] = shader.get_mode()
	after["uniforms"] = diagnosed.get("uniforms")
	after["required_uniform"] = required
	after["material_class"] = mat.get_class()
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["durable"] = shader_path.ends_with(".gdshader") or _is_external_res(shader_path)
	var param_names: Array = diagnosed.get("uniforms") as Array
	var i: int = 0
	var readback: Dictionary = {}
	while i < param_names.size():
		var uname: String = str(param_names[i])
		var got: Variant = mat.get_shader_parameter(uname)
		if got is Color:
			var c: Color = got
			readback[uname] = {"r": c.r, "g": c.g, "b": c.b, "a": c.a}
		elif got is float or got is int:
			readback[uname] = got
		i += 1
	after["parameters"] = readback
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _particles(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null or not (node is GPUParticles2D):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"render.particles requires GPUParticles2D",
			"params.node_path",
		)
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var particles: GPUParticles2D = node as GPUParticles2D
	var proc_path: String = str(params.get("process_material", ""))
	var tex_path: String = str(params.get("texture", ""))
	if proc_path.contains("::") or tex_path.contains("::"):
		return _unverified(command_id, "refusing RAM-only render durable ACK")
	var proc_hold: Dictionary = _ensure_process_material(command_id, particles, proc_path)
	if proc_hold.get("ok", false) != true:
		return proc_hold
	var proc: ParticleProcessMaterial = proc_hold.get("material") as ParticleProcessMaterial
	var stroke: ParticlesStroke = ParticlesStroke.new()
	stroke.particles = particles
	stroke.old_amount = particles.amount
	stroke.old_life = particles.lifetime
	stroke.old_proc = particles.process_material
	stroke.new_amount = int(params.get("amount", particles.amount))
	stroke.new_life = float(params.get("lifetime", particles.lifetime))
	stroke.new_proc = proc
	if not tex_path.is_empty():
		var tex: Resource = _load_res(tex_path)
		if tex == null or not (tex is Texture2D):
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "texture must be Texture2D", "params.texture")
		if not (tex is PlaceholderTexture2D) and not (tex is GradientTexture2D):
			return _errors.fail(
				command_id,
				HHAgentErrors.E_INVALID_TYPE,
				"particles texture must be PlaceholderTexture2D or GradientTexture2D",
				"params.texture",
			)
		stroke.tex_set = true
		stroke.old_tex = particles.texture
		stroke.new_tex = tex as Texture2D
	var action_name: String = "%srender.particles" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	if _is_external_res(proc_path) and particles.process_material is ParticleProcessMaterial:
		persisted = _persist_res(command_id, particles.process_material, proc_path)
		if persisted.get("ok", false) != true:
			return persisted
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _render_after(edited, params, particles)
	after["amount"] = particles.amount
	after["lifetime"] = particles.lifetime
	after["process_material_class"] = particles.process_material.get_class() if particles.process_material != null else ""
	after["texture_class"] = particles.texture.get_class() if particles.texture != null else ""
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["durable"] = _is_external_res(proc_path)
	var packed: Dictionary = engine_world_rect(particles)
	if packed.get("ok", false) == true and packed.get("invented_box", false) != true:
		var rect_v: Variant = packed.get("rect")
		if rect_v is Rect2:
			after["rect"] = _xywh(rect_v)
			after["rect_source"] = str(packed.get("rect_source", ""))
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _quality(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "quality node not found")
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var method_s: String = RenderingServer.get_current_rendering_method()
	var compat: bool = method_s == "gl_compatibility"
	var want_glow: bool = params.get("glow", false) == true
	var want_vol: bool = params.get("volumetric", false) == true
	var fallback: bool = compat and (want_glow or want_vol)
	var stroke: QualityStroke = QualityStroke.new()
	if node is PointLight2D:
		var light: PointLight2D = node as PointLight2D
		stroke.light = light
		stroke.light_set = true
		stroke.old_energy = light.energy
		stroke.old_color = light.color
		stroke.old_shadow = light.shadow_enabled
		stroke.new_energy = float(params.get("energy", light.energy))
		stroke.new_shadow = params.get("shadow_enabled", light.shadow_enabled) == true
		if params.has("color"):
			var decoded: Dictionary = _color_param(command_id, params.get("color"), "params.color")
			if decoded.get("ok", false) != true:
				return decoded
			stroke.new_color = decoded.get("color") as Color
		else:
			stroke.new_color = light.color
	elif node is CanvasModulate:
		var mod: CanvasModulate = node as CanvasModulate
		stroke.modulate = mod
		stroke.mod_set = true
		stroke.old_mod = mod.color
		if params.has("color"):
			var decoded_m: Dictionary = _color_param(command_id, params.get("color"), "params.color")
			if decoded_m.get("ok", false) != true:
				return decoded_m
			stroke.new_mod = decoded_m.get("color") as Color
		else:
			stroke.new_mod = mod.color
	elif node is WorldEnvironment:
		var we: WorldEnvironment = node as WorldEnvironment
		stroke.env_node = we
		stroke.env_set = true
		stroke.old_env = we.environment
		var env_hold: Dictionary = _ensure_environment(command_id, we, str(params.get("environment", "")), compat, want_glow, want_vol)
		if env_hold.get("ok", false) != true:
			return env_hold
		stroke.new_env = env_hold.get("environment") as Environment
		fallback = env_hold.get("fallback_applied", fallback) == true
	else:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"render.quality requires PointLight2D, CanvasModulate, or WorldEnvironment",
			"params.node_path",
		)
	var env_path: String = str(params.get("environment", ""))
	if env_path.contains("::"):
		return _unverified(command_id, "refusing RAM-only render durable ACK")
	var action_name: String = "%srender.quality" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	if node is WorldEnvironment and _is_external_res(env_path):
		var live_env: Environment = (node as WorldEnvironment).environment
		if live_env != null:
			persisted = _persist_res(command_id, live_env, env_path)
			if persisted.get("ok", false) != true:
				return persisted
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _render_after(edited, params, node)
	after["rendering_method"] = method_s
	after["fallback_applied"] = fallback
	after["glow_applied"] = want_glow and not compat
	after["volumetric_applied"] = want_vol and not compat
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["durable"] = _is_external_res(env_path)
	if node is PointLight2D:
		var live_l: PointLight2D = node as PointLight2D
		after["energy"] = live_l.energy
		after["color"] = _color_json(live_l.color)
		after["shadow_enabled"] = live_l.shadow_enabled
	if node is CanvasModulate:
		after["color"] = _color_json((node as CanvasModulate).color)
	if node is WorldEnvironment:
		var env: Environment = (node as WorldEnvironment).environment
		after["has_environment"] = env != null
		if env != null:
			after["glow_enabled"] = env.glow_enabled
			after["volumetric_fog_enabled"] = env.volumetric_fog_enabled
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _diagnose_shader(command_id: String, code: String, required: String) -> Dictionary:
	if code.strip_edges().is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "shader code is empty", "params.code")
	if not _has_shader_type(code):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"shader missing shader_type; refuse silent-ok",
			"params.code",
		)
	if _looks_garbage(code):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"shader source is garbage; refuse silent-ok",
			"params.code",
		)
	var shader: Shader = Shader.new()
	shader.code = code
	return _bind_shader_diag(command_id, shader, required)


func _bind_shader_diag(command_id: String, shader: Shader, required: String) -> Dictionary:
	if shader == null:
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "shader resource missing", "params.shader")
	var mode: int = shader.get_mode()
	if mode != Shader.MODE_CANVAS_ITEM:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"shader get_mode is not MODE_CANVAS_ITEM; refuse silent-ok",
			"params.shader",
		)
	var uniforms: Array = _uniform_names(shader)
	if not required.is_empty() and not uniforms.has(required):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_MISSING_REQUIRED,
			"required shader uniform %s absent; refuse silent-ok" % required,
			"params.required_uniform",
		)
	return {"ok": true, "shader": shader, "mode": mode, "uniforms": uniforms}


func _has_shader_type(code: String) -> bool:
	return code.contains("shader_type")


func _looks_garbage(code: String) -> bool:
	var stripped: String = code.strip_edges()
	if stripped.contains("shader_type"):
		return false
	return true


func _uniform_names(shader: Shader) -> Array:
	var out: Array = []
	var raw: Array = shader.get_shader_uniform_list()
	var i: int = 0
	while i < raw.size():
		var item_v: Variant = raw[i]
		if item_v is Dictionary:
			var name_s: String = str((item_v as Dictionary).get("name", ""))
			if name_s.begins_with("shader_parameter/"):
				name_s = name_s.trim_prefix("shader_parameter/")
			if not name_s.is_empty():
				out.append(name_s)
		elif typeof(item_v) == TYPE_STRING:
			out.append(str(item_v))
		i += 1
	return out


func _apply_shader_params(command_id: String, mat: ShaderMaterial, params: Dictionary) -> Dictionary:
	var raw: Variant = params.get("parameters", {})
	if typeof(raw) != TYPE_DICTIONARY:
		return {"ok": true}
	var rec: Dictionary = raw
	for key_s: String in rec.keys():
		var value_v: Variant = rec[key_s]
		if value_v is Dictionary:
			var d: Dictionary = value_v
			if d.has("r") and d.has("g") and d.has("b"):
				var decoded: Dictionary = _color_param(command_id, d, "params.parameters")
				if decoded.get("ok", false) != true:
					return decoded
				mat.set_shader_parameter(key_s, decoded.get("color"))
				continue
			if d.has("schema") or d.has("type"):
				var enc: Dictionary = _codec.decode(d, "params.parameters/%s" % key_s)
				if enc.get("ok", false) != true:
					return _fail_enc(command_id, enc)
				mat.set_shader_parameter(key_s, enc.get("value"))
				continue
		mat.set_shader_parameter(key_s, value_v)
	return {"ok": true}


func _ensure_process_material(command_id: String, particles: GPUParticles2D, proc_path: String) -> Dictionary:
	if not proc_path.is_empty():
		if FileAccess.file_exists(proc_path) or ResourceLoader.exists(proc_path):
			var jail: Dictionary = _meta.jail(command_id, proc_path)
			if jail.get("ok", false) != true:
				return jail
			var res: Resource = _load_res(proc_path)
			if res == null or not (res is ParticleProcessMaterial):
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "process_material is not ParticleProcessMaterial", proc_path)
			return {"ok": true, "material": res as ParticleProcessMaterial}
		var created_jail: Dictionary = _meta.jail(command_id, proc_path)
		if created_jail.get("ok", false) != true:
			return created_jail
		if not _is_external_res(proc_path):
			return _errors.fail(command_id, HHAgentErrors.E_PATH, "ParticleProcessMaterial persist requires .tres or .res", proc_path)
		return {"ok": true, "material": ParticleProcessMaterial.new()}
	if particles.process_material is ParticleProcessMaterial:
		return {"ok": true, "material": particles.process_material as ParticleProcessMaterial}
	return {"ok": true, "material": ParticleProcessMaterial.new()}


func _ensure_environment(
	command_id: String,
	we: WorldEnvironment,
	env_path: String,
	compat: bool,
	want_glow: bool,
	want_vol: bool,
) -> Dictionary:
	var env: Environment = null
	if not env_path.is_empty():
		if FileAccess.file_exists(env_path) or ResourceLoader.exists(env_path):
			var jail: Dictionary = _meta.jail(command_id, env_path)
			if jail.get("ok", false) != true:
				return jail
			var res: Resource = _load_res(env_path)
			if res == null or not (res is Environment):
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "environment is not Environment", env_path)
			env = res as Environment
		else:
			var created_jail: Dictionary = _meta.jail(command_id, env_path)
			if created_jail.get("ok", false) != true:
				return created_jail
			if not _is_external_res(env_path):
				return _errors.fail(command_id, HHAgentErrors.E_PATH, "Environment persist requires .tres or .res", env_path)
			env = Environment.new()
	elif we.environment != null:
		env = we.environment
	else:
		env = Environment.new()
	var fallback: bool = false
	if compat:
		fallback = want_glow or want_vol
		env.glow_enabled = false
		env.volumetric_fog_enabled = false
	else:
		if want_glow:
			env.glow_enabled = true
		if want_vol:
			env.volumetric_fog_enabled = true
	return {"ok": true, "environment": env, "fallback_applied": fallback}


func _atomic_shader_text(command_id: String, dest: String, contents: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, dest)
	if jail.get("ok", false) != true:
		return jail
	if not dest.ends_with(".gdshader"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "shader text persist requires .gdshader", dest)
	var bytes: PackedByteArray = contents.to_utf8_buffer()
	if bytes.size() >= 3 and bytes[0] == 0xEF and bytes[1] == 0xBB and bytes[2] == 0xBF:
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "UTF-8 BOM is not allowed", dest)
	var dir_err: Error = _meta.ensure_parent_dir(dest)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create shader directory", dest)
	var tmp: String = dest + ".tmp"
	var bak: String = dest + ".hh-bak"
	var tmp_abs: String = ProjectSettings.globalize_path(tmp)
	var dest_abs: String = ProjectSettings.globalize_path(dest)
	var bak_abs: String = ProjectSettings.globalize_path(bak)
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp_abs)
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot open shader tmp", tmp)
	f.store_string(contents)
	f.flush()
	f.close()
	var tmp_text: String = FileAccess.get_file_as_string(tmp)
	if tmp_text != contents:
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "tmp write did not match intended shader bytes")
	var existed: bool = FileAccess.file_exists(dest)
	if existed:
		if FileAccess.file_exists(bak):
			DirAccess.remove_absolute(bak_abs)
		var bak_err: Error = DirAccess.rename_absolute(dest_abs, bak_abs)
		if bak_err != OK:
			DirAccess.remove_absolute(tmp_abs)
			return _unverified(command_id, "could not park existing shader for atomic replace")
	var ren: Error = DirAccess.rename_absolute(tmp_abs, dest_abs)
	if ren != OK:
		if existed:
			DirAccess.rename_absolute(bak_abs, dest_abs)
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "atomic rename failed: %s" % error_string(ren))
	if existed and FileAccess.file_exists(bak):
		DirAccess.remove_absolute(bak_abs)
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp_abs)
	if not FileAccess.file_exists(dest):
		return _unverified(command_id, "dest missing after atomic rename")
	_meta.refresh_fs(dest)
	var disk: String = _meta.disk_hash(dest)
	if disk.is_empty() or disk == "missing":
		return _unverified(command_id, "shader disk hash missing after save")
	return {"ok": true, "disk_hash": disk, "path": dest}


func _render_after(edited: Node, params: Dictionary, node: Node) -> Dictionary:
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["class_name"] = node.get_class() if node != null else ""
	after["path"] = str(params.get("node_path", ""))
	after["invented_box"] = false
	after["used_engine_transform"] = true
	after["source"] = "editor"
	var packed: Dictionary = engine_world_rect(node)
	if packed.get("ok", false) == true and packed.get("invented_box", false) != true:
		var rect_v: Variant = packed.get("rect")
		if rect_v is Rect2:
			after["rect"] = _xywh(rect_v)
			after["rect_source"] = str(packed.get("rect_source", ""))
	return after


func _color_param(command_id: String, raw: Variant, path_s: String) -> Dictionary:
	if raw is Dictionary:
		var d: Dictionary = raw
		if d.has("schema") or str(d.get("type", "")) == "Color":
			var enc: Dictionary = _codec.decode(d, path_s)
			if enc.get("ok", false) != true:
				return _fail_enc(command_id, enc)
			if not (enc.get("value") is Color):
				return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "color must be Color", path_s)
			return {"ok": true, "color": enc.get("value")}
		return {
			"ok": true,
			"color": Color(float(d.get("r", 1.0)), float(d.get("g", 1.0)), float(d.get("b", 1.0)), float(d.get("a", 1.0))),
		}
	return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "color must be an object", path_s)


func _color_json(c: Color) -> Dictionary:
	return {"r": c.r, "g": c.g, "b": c.b, "a": c.a}


func _commit_stroke(command_id: String, edited: Node, action_name: String, stroke: RefCounted) -> Dictionary:
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(stroke, "apply")
	mgr.add_undo_method(stroke, "revert")
	mgr.add_do_reference(stroke)
	mgr.commit_action()
	return {"ok": true}


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


func _persist_res(command_id: String, res: Resource, res_path: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not _is_external_res(res_path):
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


func _is_external_res(path_s: String) -> bool:
	return (path_s.ends_with(".tres") or path_s.ends_with(".res")) and not path_s.contains("::")


func _xywh(r: Rect2) -> Dictionary:
	return {"x": r.position.x, "y": r.position.y, "w": r.size.x, "h": r.size.y}


func _mgr() -> EditorUndoRedoManager:
	return EditorInterface.get_editor_undo_redo()


func _fail_enc(command_id: String, enc: Dictionary) -> Dictionary:
	var err_v: Variant = enc.get("error", {})
	if err_v is Dictionary:
		var err: Dictionary = err_v
		return _errors.fail(command_id, str(err.get("code", HHAgentErrors.E_INVALID_VARIANT)), str(err.get("message", "variant")), str(err.get("path", "")))
	return _unverified(command_id, "variant codec failed")


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out


static func _rect_fail() -> Dictionary:
	return {
		"ok": false,
		"rect": Rect2(),
		"rect_source": "none",
		"invented_box": false,
		"used_engine_transform": false,
	}


static func _particles_world_rect(p: GPUParticles2D) -> Dictionary:
	if p == null:
		return _rect_fail()
	# GPUParticles2D has no typed get_rect() in 4.7.1. Engine AABB is
	# visibility_rect; texture.get_size is the fallback. Never invent 32px.
	var local: Rect2 = p.visibility_rect
	var source_s: String = "visibility_rect"
	if local.size.x <= 0.0 or local.size.y <= 0.0:
		if p.texture != null:
			var sz: Vector2 = p.texture.get_size()
			if sz.x > 0.0 and sz.y > 0.0:
				local = Rect2(-sz * 0.5, sz)
				source_s = "get_rect"
	if local.size.x <= 0.0 or local.size.y <= 0.0:
		return _rect_fail()
	return {
		"ok": true,
		"rect": p.get_global_transform() * local,
		"rect_source": source_s,
		"invented_box": false,
		"used_engine_transform": true,
	}
