class_name MatchHudController
extends CanvasLayer
## Superfighters Y8 Authentic Match HUD Controller (SF-M5 / SF-M8).
## Renders top-screen player/bot status panels (HP bar in red, Stamina bar in yellow/cyan,
## character name, active weapon & ammo e.g. 'JOHNNY — PISTOL [12]' or 'UNARMED'),
## center round banner ('GET READY...', 'FIGHT!', 'PLAYER 1 WINS!', 'STAGE CLEAR!', 'DRAW GAME!'),
## Stage / Survival wave counters, world-space overhead mini HP/Stamina bars (PlayerBars.as),
## and floating pickup text signs (TextSign.as).

const MapLoaderScript = preload("res://game/world/map_loader.gd")
const _PreloadTacticalStrikerRigPainter = preload("res://game/fighter/tactical_striker_rig_painter.gd")

var match_world: Node2D = null
var _hud_canvas: Control = null
var _font: Font = null
var _last_hp_by_id: Dictionary = {}
var _hp_bar_timer_by_id: Dictionary = {}
var _trailing_hp_by_id: Dictionary = {}
var _last_expr_key_by_id: Dictionary = {}
var _expr_pop_timer_by_id: Dictionary = {}


func get_fighter_active_expression_key(fighter: Node2D) -> String:
	if fighter == null or not is_instance_valid(fighter):
		return "confident"
	var rv: Node = fighter.get("rig_view") as Node
	if rv != null and rv.has_method("get_current_hud_portrait_key"):
		return str(rv.call("get_current_hud_portrait_key"))
	return "confident"


class HudDrawSurface extends Control:
	var hud: CanvasLayer = null

	func _draw() -> void:
		if hud == null:
			return
		hud.call("_draw_hud_surface", self)


func _ready() -> void:
	layer = 15
	_load_hud_font()
	_ensure_surface()


func _load_hud_font() -> void:
	var font_paths: Array[String] = [
		"res://assets/fonts/12_PF Arma Five.ttf",
		"res://assets/fonts/106_04b03.ttf",
		"res://assets/fonts/530_PF Tempesta Seven.ttf",
		"res://assets/fonts/33_Verdana.ttf",
	]
	for fp: String in font_paths:
		if ResourceLoader.exists(fp):
			var f: Resource = ResourceLoader.load(fp)
			if f is Font:
				_font = f as Font
				break


func _ensure_surface() -> void:
	if _hud_canvas == null or not is_instance_valid(_hud_canvas):
		var surf: HudDrawSurface = HudDrawSurface.new()
		surf.name = "HudDrawSurface"
		surf.set_anchors_preset(Control.PRESET_FULL_RECT)
		surf.mouse_filter = Control.MOUSE_FILTER_IGNORE
		surf.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		surf.hud = self
		_hud_canvas = surf
		add_child(_hud_canvas)


func update_hud() -> void:
	_ensure_surface()
	if _hud_canvas != null and is_instance_valid(_hud_canvas):
		_hud_canvas.queue_redraw()


func format_fighter_weapon_label(fighter: Node2D) -> String:
	if fighter == null or not is_instance_valid(fighter):
		return "UNARMED"
	var dname: String = str(fighter.get("display_name")).to_upper()
	if dname.is_empty():
		dname = str(fighter.get("character_id")).to_upper()
	if dname.is_empty():
		dname = "FIGHTER"

	var wid: String = ""
	var ammo: int = -1
	if fighter.has_method("get_active_weapon_id"):
		wid = str(fighter.call("get_active_weapon_id")).to_upper()
	if fighter.has_method("get_active_weapon_ammo"):
		ammo = int(fighter.call("get_active_weapon_ammo"))

	if wid.is_empty():
		var inv_var: Variant = fighter.get("inventory")
		var ammo_var: Variant = fighter.get("inventory_ammo")
		if typeof(inv_var) == TYPE_DICTIONARY and typeof(ammo_var) == TYPE_DICTIONARY:
			var inv: Dictionary = inv_var as Dictionary
			var am: Dictionary = ammo_var as Dictionary
			var active_slot: int = int(fighter.get("active_gun_slot")) if fighter.get("active_gun_slot") != null else 2
			if not str(inv.get(active_slot, "")).is_empty() and int(am.get(active_slot, 0)) > 0:
				wid = str(inv.get(active_slot, "")).to_upper()
				ammo = int(am.get(active_slot, 0))
			elif not str(inv.get(3, "")).is_empty() and int(am.get(3, 0)) > 0:
				wid = str(inv.get(3, "")).to_upper()
				ammo = int(am.get(3, 0))
			elif not str(inv.get(2, "")).is_empty() and int(am.get(2, 0)) > 0:
				wid = str(inv.get(2, "")).to_upper()
				ammo = int(am.get(2, 0))
			else:
				wid = str(inv.get(1, "FISTS")).to_upper()
				ammo = int(am.get(1, -1))

	if wid.is_empty() or wid == "FISTS" or wid == "UNARMED":
		return dname + " — UNARMED"

	var wdata: Dictionary = MapLoaderScript.get_registry().call("get_weapon_data", wid) as Dictionary
	var w_label: String = str(wdata.get("display_name", wid)).to_upper()
	if ammo >= 0:
		return dname + " — " + w_label + " [" + str(ammo) + "]"
	return dname + " — " + w_label


func _get_hp_bar_color(hp_ratio: float) -> Color:
	if hp_ratio >= 0.5:
		var t: float = clampf((hp_ratio - 0.5) * 2.0, 0.0, 1.0)
		return Color(1.0 - 0.72 * t, 0.88, 0.18, 0.96)
	var t2: float = clampf(hp_ratio * 2.0, 0.0, 1.0)
	return Color(0.95, 0.15 + 0.73 * t2, 0.12, 0.96)


func _draw_hud_surface(canvas: Control) -> void:
	if match_world == null or not is_instance_valid(match_world):
		return

	var vp_size: Vector2 = canvas.get_viewport_rect().size
	if vp_size.x <= 0.0 or vp_size.y <= 0.0:
		vp_size = Vector2(650.0, 400.0)

	var font: Font = _font if _font != null else ThemeDB.fallback_font
	var fighters_var: Variant = match_world.get("fighters")
	var fighters: Array = fighters_var as Array if typeof(fighters_var) == TYPE_ARRAY else []
	var ui_scale: float = clampf(vp_size.y / 400.0, 1.0, 1.5)
	var strip_h: float = 42.0 * ui_scale

	# 1. Top status strip background
	canvas.draw_rect(Rect2(0.0, 0.0, vp_size.x, strip_h), Color(0.05, 0.05, 0.07, 0.84), true)
	canvas.draw_line(Vector2(0.0, strip_h), Vector2(vp_size.x, strip_h), Color(0.36, 0.4, 0.48, 0.9), 1.5)

	# 2. Draw fighter status cards across the top (excluding temporary summoned clones so HUD cards never shrink)
	var hud_fighters: Array[Node2D] = []
	for hf_var: Variant in fighters:
		if hf_var is Node2D and is_instance_valid(hf_var) and not bool((hf_var as Node2D).get("is_summoned_clone")):
			hud_fighters.append(hf_var as Node2D)
	var count: int = mini(hud_fighters.size(), 8)
	if count > 0:
		var margin_x: float = 10.0 * ui_scale
		var gap_x: float = 8.0 * ui_scale
		var card_w: float = clampf((vp_size.x - margin_x * 2.0 - gap_x * float(max(0, count - 1))) / float(count), 115.0 * ui_scale, 250.0 * ui_scale)
		for i: int in range(count):
			var f: Node2D = hud_fighters[i]
			var card_x: float = margin_x + float(i) * (card_w + gap_x)
			if count == 2 and i == 1:
				card_x = vp_size.x - margin_x - card_w
			_draw_fighter_card(canvas, font, f, i, Rect2(card_x, 3.0 * ui_scale, card_w, 35.0 * ui_scale))

	# 3. Mode header info (Stage 1..12 or Survival Wave & Kills)
	var gmode: String = str(match_world.get("game_mode"))
	var mode_badge: String = ""
	if gmode == "stage":
		var st_lvl: int = int(match_world.get("stage_level")) if match_world.get("stage_level") != null else 1
		mode_badge = "STAGE " + str(st_lvl) + " / 12"
	elif gmode == "survival":
		var wave: int = int(match_world.get("survival_wave")) if match_world.get("survival_wave") != null else 1
		var kills: int = int(match_world.get("survival_kills")) if match_world.get("survival_kills") != null else 0
		mode_badge = "SURVIVAL WAVE " + str(wave) + " — KILLS: " + str(kills)

	if not mode_badge.is_empty():
		var bw: float = 190.0 * ui_scale
		var bh: float = 18.0 * ui_scale
		var badge_rect: Rect2 = Rect2(vp_size.x * 0.5 - bw * 0.5, strip_h + 4.0, bw, bh)
		canvas.draw_rect(badge_rect, Color(0.08, 0.09, 0.12, 0.86), true)
		canvas.draw_rect(badge_rect, Color(0.88, 0.75, 0.28, 0.85), false, 1.0)
		canvas.draw_string(
			font,
			Vector2(badge_rect.position.x + 8.0, badge_rect.position.y + bh * 0.72),
			mode_badge,
			HORIZONTAL_ALIGNMENT_CENTER,
			badge_rect.size.x - 16.0,
			int(8.0 * ui_scale),
			Color(0.98, 0.9, 0.45, 1.0)
		)

	# 4. World-space overhead mini bars (PlayerBars.as) & Floating Pickup Texts (TextSign.as)
	var intro_timer: float = float(match_world.get("overhead_label_timer")) if match_world.get("overhead_label_timer") != null else 0.0
	var cam: Camera2D = match_world.get("dynamic_camera") as Camera2D
	if cam != null and is_instance_valid(cam):
		var cam_pos: Vector2 = cam.global_position
		var cam_zoom: Vector2 = cam.zoom
		var half_vp: Vector2 = vp_size * 0.5
		var zoom_scale: float = clampf(cam_zoom.x, 1.0, 3.0)

		for i: int in range(fighters.size()):
			var f_var: Variant = fighters[i]
			if not (f_var is Node2D) or not is_instance_valid(f_var):
				continue
			var f: Node2D = f_var as Node2D
			if bool(f.get("is_dead")):
				continue

			var fid: int = f.get_instance_id()
			var cur_hp: float = clampf(float(f.get("hp")) if f.get("hp") != null else 100.0, 0.0, 200.0)
			var max_hp: float = maxf(1.0, float(f.get("max_hp")) if f.get("max_hp") != null else 100.0)
			var prev_hp: float = float(_last_hp_by_id.get(fid, cur_hp))
			var hp_timer: float = float(_hp_bar_timer_by_id.get(fid, 0.0))
			if absf(cur_hp - prev_hp) > 0.05:
				hp_timer = 35.0
			elif hp_timer > 0.0:
				hp_timer = maxf(0.0, hp_timer - 0.5)
			_last_hp_by_id[fid] = cur_hp
			_hp_bar_timer_by_id[fid] = hp_timer
			var trail_hp: float = float(_trailing_hp_by_id.get(fid, cur_hp))
			if cur_hp < trail_hp:
				trail_hp = maxf(cur_hp, move_toward(trail_hp, cur_hp, max_hp * 0.016))
			else:
				trail_hp = cur_hp
			_trailing_hp_by_id[fid] = trail_hp

			var f_dmg_timer: float = float(f.get("_hp_damage_timer")) if f.get("_hp_damage_timer") != null else 0.0
			var show_hp_bar: bool = (intro_timer > 0.0) or (hp_timer > 0.0) or (f_dmg_timer > 0.0)
			var stamina: float = clampf(float(f.get("sprint_energy")) if f.get("sprint_energy") != null else 100.0, 0.0, 100.0)
			var max_stamina: float = maxf(1.0, float(f.get("max_sprint_energy")) if f.get("max_sprint_energy") != null else 100.0)
			var show_stamina_bar: bool = stamina < 99.0

			var world_head: Vector2 = f.global_position + Vector2(0.0, -21.0)
			var screen_pt: Vector2 = (world_head - cam_pos) * cam_zoom + half_vp
			# EC-37: Clamp overhead world-space bar below the top HUD strip so high-jumping fighters stay readable
			screen_pt.y = maxf(strip_h + 14.0 * ui_scale, screen_pt.y)
			var slot_idx: int = int(f.get("slot_index")) if f.get("slot_index") != null else i
			var is_bot_f: bool = bool(f.get("is_bot"))

			# Authentic Y8 Overhead 'player_sign' (Symbol 1095.xml: white circle with '1'/'2' for humans, dot for bots)
			var sign_y: float = screen_pt.y - 9.0 * zoom_scale
			if not is_bot_f:
				var sign_r: float = maxf(6.5, 4.4 * zoom_scale)
				var sign_center: Vector2 = Vector2(screen_pt.x, sign_y)
				canvas.draw_circle(sign_center, sign_r, Color(0.08, 0.08, 0.1, 0.86))
				canvas.draw_arc(sign_center, sign_r, 0.0, TAU, 20, Color(0.98, 0.98, 1.0, 0.96), maxf(1.2, 0.8 * zoom_scale))
				var p_num: String = str(slot_idx + 1)
				var fsize_num: int = int(maxf(8.0, 5.2 * zoom_scale))
				canvas.draw_string(
					font,
					Vector2(sign_center.x - 14.0, sign_center.y + float(fsize_num) * 0.36),
					p_num,
					HORIZONTAL_ALIGNMENT_CENTER,
					28.0,
					fsize_num,
					Color(1.0, 1.0, 1.0, 1.0)
				)
			elif show_hp_bar:
				canvas.draw_circle(Vector2(screen_pt.x, sign_y + 2.0 * zoom_scale), maxf(2.0, 1.3 * zoom_scale), Color(0.95, 0.95, 0.98, 0.9))

			# Mini 20x2 px world-space HP bar (scaled by camera zoom) + LoL White Damage Sub-Bar Trail
			var bw_px: float = 20.0 * zoom_scale
			var bh_px: float = maxf(2.0, 2.0 * zoom_scale)
			var bx: float = screen_pt.x - bw_px * 0.5
			var by: float = screen_pt.y - 3.5 * zoom_scale

			if show_hp_bar:
				var hp_ratio: float = clampf(cur_hp / max_hp, 0.0, 1.0)
				var trail_ratio: float = clampf(trail_hp / max_hp, hp_ratio, 1.0)
				var hp_bg: Rect2 = Rect2(bx - 1.0, by - 1.0, bw_px + 2.0, bh_px + 2.0)
				canvas.draw_rect(hp_bg, Color(0.04, 0.04, 0.05, 0.92), true)
				canvas.draw_rect(Rect2(bx, by, bw_px, bh_px), Color(0.22, 0.08, 0.08, 0.92), true)
				if trail_ratio > hp_ratio + 0.005:
					canvas.draw_rect(Rect2(bx, by, bw_px * trail_ratio, bh_px), Color(1.0, 0.96, 0.9, 0.92), true)
				canvas.draw_rect(Rect2(bx, by, bw_px * hp_ratio, bh_px), _get_hp_bar_color(hp_ratio), true)

			# Mini 20x1.5 px world-space Stamina bar below HP bar when sprint_energy < 99
			if show_stamina_bar:
				var st_ratio: float = clampf(stamina / max_stamina, 0.0, 1.0)
				var sh_px: float = maxf(1.5, 1.5 * zoom_scale)
				var sy: float = by + bh_px + 1.5
				canvas.draw_rect(Rect2(bx - 1.0, sy - 0.5, bw_px + 2.0, sh_px + 1.0), Color(0.04, 0.04, 0.05, 0.88), true)
				canvas.draw_rect(Rect2(bx, sy, bw_px, sh_px), Color(0.16, 0.16, 0.1, 0.9), true)
				canvas.draw_rect(Rect2(bx, sy, bw_px * st_ratio, sh_px), Color(0.98, 0.86, 0.24, 0.96), true)

			# Mini world-space LoL Resource Bar & Secondary Pips for Powered Fighters
			if bool(f.get("is_powered_fighter")):
				var r_val: float = float(f.get("resource_val")) if f.get("resource_val") != null else 0.0
				var r_max: float = maxf(1.0, float(f.get("resource_max")) if f.get("resource_max") != null else 100.0)
				var r_ratio: float = clampf(r_val / r_max, 0.0, 1.0)
				var r_spec: Dictionary = f.get("resource_spec") as Dictionary if typeof(f.get("resource_spec")) == TYPE_DICTIONARY else {}
				var r_col: Color = Color.from_string(str(r_spec.get("bar_color", "#FFCC22")), Color(1.0, 0.82, 0.22, 0.96))
				if float(f.get("overheat_timer")) > 0.0:
					r_col = Color(1.0, 0.22, 0.15, 0.98)
				var ry_px: float = by + bh_px + (4.2 if show_stamina_bar else 1.8)
				var rh_px: float = maxf(1.5, 1.4 * zoom_scale)
				canvas.draw_rect(Rect2(bx - 1.0, ry_px - 0.5, bw_px + 2.0, rh_px + 1.0), Color(0.04, 0.04, 0.05, 0.88), true)
				canvas.draw_rect(Rect2(bx, ry_px, bw_px * r_ratio, rh_px), r_col, true)
				var pips_max: int = int(f.get("secondary_pips_max")) if f.get("secondary_pips_max") != null else 0
				var pips_cur: int = int(f.get("secondary_pips")) if f.get("secondary_pips") != null else 0
				if pips_max > 0:
					var pip_w: float = (bw_px - float(pips_max - 1)) / float(pips_max)
					var py_px: float = ry_px + rh_px + 1.5
					for p_i: int in range(pips_max):
						var px_i: float = bx + float(p_i) * (pip_w + 1.0)
						var p_fill: Color = Color(1.0, 0.92, 0.32, 0.98) if p_i < pips_cur else Color(0.18, 0.18, 0.22, 0.78)
						canvas.draw_rect(Rect2(px_i, py_px, maxf(1.2, pip_w), maxf(1.2, 1.1 * zoom_scale)), p_fill, true)

		# Floating pickup texts (TextSign.as: e.g. 'SHOTGUN', '+HP', 'SLOMO')
		var ft_var: Variant = match_world.get("floating_texts")
		if typeof(ft_var) == TYPE_ARRAY:
			for ft_item: Variant in ft_var as Array:
				if typeof(ft_item) != TYPE_DICTIONARY:
					continue
				var ft: Dictionary = ft_item as Dictionary
				var wpos: Vector2 = ft.get("pos", Vector2.ZERO) as Vector2
				var spt: Vector2 = (wpos - cam_pos) * cam_zoom + half_vp
				var txt: String = str(ft.get("text", ""))
				var col: Color = ft.get("color", Color(1.0, 0.94, 0.42, 1.0)) as Color
				var age: float = float(ft.get("age", 0.0))
				var max_a: float = maxf(1.0, float(ft.get("max_age", 24.0)))
				var alpha: float = clampf(1.2 - age / max_a, 0.0, 1.0)
				var fsize: int = int(maxf(8.0, 5.0 * zoom_scale))
				canvas.draw_string(
					font,
					Vector2(spt.x - 49.0, spt.y + 1.0),
					txt,
					HORIZONTAL_ALIGNMENT_CENTER,
					100.0,
					fsize,
					Color(0.0, 0.0, 0.0, alpha * 0.9)
				)
				canvas.draw_string(
					font,
					Vector2(spt.x - 50.0, spt.y),
					txt,
					HORIZONTAL_ALIGNMENT_CENTER,
					100.0,
					fsize,
					Color(col.r, col.g, col.b, alpha)
				)

	# 4b. Anime Ultimate Cut-In Banner (SA-WP11 & EC-32: Non-Blocking Angled Parallelogram Strip + Dual Clash Split Cut-In!)
	var cutins_list: Array = []
	var cis_var: Variant = match_world.get("active_cutins")
	if typeof(cis_var) == TYPE_ARRAY and not (cis_var as Array).is_empty():
		for item_ci: Variant in cis_var as Array:
			if typeof(item_ci) == TYPE_DICTIONARY and float((item_ci as Dictionary).get("timer", 0.0)) > 0.0:
				cutins_list.append(item_ci as Dictionary)
	if cutins_list.is_empty():
		var cutin_var: Variant = match_world.get("active_cutin")
		if typeof(cutin_var) == TYPE_DICTIONARY and not (cutin_var as Dictionary).is_empty():
			var cd_single: Dictionary = cutin_var as Dictionary
			if float(cd_single.get("timer", 0.0)) > 0.0:
				cutins_list.append(cd_single)

	if not cutins_list.is_empty():
		var c_h: float = 54.0 * ui_scale
		var c_y: float = strip_h + 6.0 * ui_scale
		var slant_dx: float = 18.0 * ui_scale
		var reg_ci: Node = MapLoaderScript.get_registry()
		var is_dual_clash: bool = cutins_list.size() >= 2
		for ci_idx: int in range(mini(cutins_list.size(), 2)):
			var cd: Dictionary = cutins_list[ci_idx] as Dictionary
			var c_timer: float = float(cd.get("timer", 0.0))
			var c_max: float = maxf(0.05, float(cd.get("max_timer", 0.42)))
			var c_alpha: float = clampf(c_timer / (c_max * 0.32), 0.0, 1.0)
			var c_col: Color = cd.get("color", Color(1.0, 0.82, 0.22, 1.0)) as Color
			var x_start: float = 0.0 if (not is_dual_clash or ci_idx == 0) else (vp_size.x * 0.5 + 4.0 * ui_scale)
			var x_end: float = vp_size.x if not is_dual_clash else (vp_size.x * 0.5 - 4.0 * ui_scale if ci_idx == 0 else vp_size.x)
			var poly_pts: PackedVector2Array = PackedVector2Array([
				Vector2(x_start + slant_dx, c_y),
				Vector2(x_end, c_y),
				Vector2(maxf(x_start, x_end - slant_dx), c_y + c_h),
				Vector2(x_start, c_y + c_h),
			])
			canvas.draw_colored_polygon(poly_pts, Color(0.03, 0.04, 0.07, 0.88 * c_alpha))
			# Diagonal speedlines across the cut-in strip
			var span_w: float = maxf(40.0, x_end - x_start)
			for sl_i: int in range(6):
				var sl_x: float = x_start + span_w * (0.12 + float(sl_i) * 0.15)
				canvas.draw_line(
					Vector2(sl_x + slant_dx * 0.6, c_y + 2.0),
					Vector2(sl_x - slant_dx * 0.6, c_y + c_h - 2.0),
					Color(c_col.r, c_col.g, c_col.b, 0.24 * c_alpha),
					1.5
				)
			canvas.draw_line(Vector2(x_start + slant_dx, c_y), Vector2(x_end, c_y), Color(c_col.r, c_col.g, c_col.b, c_alpha), 2.2)
			canvas.draw_line(Vector2(x_start, c_y + c_h), Vector2(maxf(x_start, x_end - slant_dx), c_y + c_h), Color(1.0, 0.96, 0.82, c_alpha), 1.8)
			var banner_path: String = str(cd.get("banner_path", ""))
			var bw_img: float = minf(span_w * 0.44, 195.0 * ui_scale)
			if reg_ci != null and not banner_path.is_empty():
				var btex: Texture2D = reg_ci.call("load_cached_texture", banner_path) as Texture2D
				if btex != null:
					canvas.draw_texture_rect(btex, Rect2(x_start + 12.0 * ui_scale, c_y + 3.0 * ui_scale, bw_img, c_h - 6.0 * ui_scale), false, Color(1.0, 1.0, 1.0, c_alpha))
			var cname_ci: String = str(cd.get("char_name", "HERO")).to_upper()
			var sname_ci: String = str(cd.get("skill_name", "ULTIMATE")).to_upper()
			var txt_x: float = x_start + bw_img + 18.0 * ui_scale
			var txt_w: float = maxf(40.0, x_end - txt_x - 8.0 * ui_scale)
			canvas.draw_string(font, Vector2(txt_x, c_y + 20.0 * ui_scale), cname_ci + " — ULTIMATE!", HORIZONTAL_ALIGNMENT_LEFT, txt_w, int(8.0 * ui_scale), Color(c_col.r, c_col.g, c_col.b, c_alpha))
			canvas.draw_string(font, Vector2(txt_x, c_y + 41.0 * ui_scale), sname_ci, HORIZONTAL_ALIGNMENT_LEFT, txt_w, int(12.0 * ui_scale), Color(1.0, 0.98, 0.88, c_alpha))
		if is_dual_clash:
			var mid_x: float = vp_size.x * 0.5
			canvas.draw_line(Vector2(mid_x + 8.0 * ui_scale, c_y - 3.0), Vector2(mid_x - 8.0 * ui_scale, c_y + c_h + 3.0), Color(1.0, 0.96, 0.4, 0.98), 3.0)

	# 5. Center Round Banner ('GET READY...', 'FIGHT!', 'PLAYER 1 WINS!', 'STAGE CLEAR!', 'DRAW GAME!')
	var rstate: String = str(match_world.get("round_state"))
	var btext: String = str(match_world.get("banner_text"))
	var btimer: float = float(match_world.get("banner_timer")) if match_world.get("banner_timer") != null else 0.0

	if (btimer > 0.0 and not btext.is_empty()) or rstate == "ROUND_OVER":
		var display_title: String = btext
		if rstate == "ROUND_OVER" and not str(match_world.get("winner_text")).is_empty():
			display_title = str(match_world.get("winner_text"))

		var box_w: float = 360.0 * ui_scale
		var box_h: float = (66.0 if rstate == "ROUND_OVER" else 44.0) * ui_scale
		var box_rect: Rect2 = Rect2((vp_size.x - box_w) * 0.5, (vp_size.y - box_h) * 0.5 - 12.0, box_w, box_h)
		canvas.draw_rect(box_rect, Color(0.04, 0.04, 0.06, 0.9), true)
		canvas.draw_rect(box_rect, Color(0.94, 0.24, 0.18, 0.96), false, 2.0)

		canvas.draw_string(
			font,
			Vector2(box_rect.position.x + 12.0, box_rect.position.y + 26.0 * ui_scale),
			display_title,
			HORIZONTAL_ALIGNMENT_CENTER,
			box_w - 24.0,
			int(14.0 * ui_scale),
			Color(1.0, 0.94, 0.78, 1.0)
		)

		if rstate == "ROUND_OVER":
			var sub_prompt: String = "[ENTER / SPACE] PLAY AGAIN     [ESC] MAIN MENU"
			if gmode == "stage" and (display_title == "STAGE CLEAR!" or "COMPLETE" in display_title):
				sub_prompt = "[ENTER / SPACE] NEXT STAGE     [ESC] MAIN MENU"
			canvas.draw_string(
				font,
				Vector2(box_rect.position.x + 12.0, box_rect.position.y + 50.0 * ui_scale),
				sub_prompt,
				HORIZONTAL_ALIGNMENT_CENTER,
				box_w - 24.0,
				int(8.0 * ui_scale),
				Color(0.8, 0.88, 0.98, 0.95)
			)


func _draw_fighter_card(
	canvas: Control,
	font: Font,
	fighter: Node2D,
	idx: int,
	rect: Rect2
) -> void:
	var ui_scale: float = clampf(rect.size.y / 35.0, 1.0, 1.5)
	canvas.draw_rect(rect, Color(0.11, 0.12, 0.15, 0.94), true)
	var team_id: int = int(fighter.get("team_id")) if fighter.get("team_id") != null else 0
	var border_col: Color = Color(0.38, 0.42, 0.48, 0.9)
	if team_id == 1:
		border_col = Color(0.28, 0.62, 0.95, 0.95)
	elif team_id == 2:
		border_col = Color(0.95, 0.35, 0.28, 0.95)
	canvas.draw_rect(rect, border_col, false, 1.5)

	var hp: float = clampf(float(fighter.get("hp")) if fighter.get("hp") != null else 100.0, 0.0, 200.0)
	var max_hp: float = maxf(1.0, float(fighter.get("max_hp")) if fighter.get("max_hp") != null else 100.0)
	var stamina: float = clampf(float(fighter.get("sprint_energy")) if fighter.get("sprint_energy") != null else 100.0, 0.0, 100.0)
	var max_stamina: float = maxf(1.0, float(fighter.get("max_sprint_energy")) if fighter.get("max_sprint_energy") != null else 100.0)

	var hp_ratio: float = clampf(hp / max_hp, 0.0, 1.0)
	var st_ratio: float = clampf(stamina / max_stamina, 0.0, 1.0)

	var reg: Node = MapLoaderScript.get_registry()
	var char_id: String = str(fighter.get("character_id")).to_lower()
	var cdata: Dictionary = reg.call("get_character_data", char_id) as Dictionary if reg != null else {}
	var head_col: Color = cdata.get("tint_head", Color(0.92, 0.78, 0.64, 1.0)) as Color
	var body_col: Color = cdata.get("tint_body", Color(0.3, 0.45, 0.75, 1.0)) as Color

	# 1. Left character live expression portrait box (TS-WP6: Live Expression Portrait + Scale Pop)
	var fid_port: int = fighter.get_instance_id()
	var expr_key: String = get_fighter_active_expression_key(fighter)
	var prev_expr_key: String = str(_last_expr_key_by_id.get(fid_port, expr_key))
	var pop_t: float = float(_expr_pop_timer_by_id.get(fid_port, 0.0))
	if expr_key != prev_expr_key:
		pop_t = 0.16
		_last_expr_key_by_id[fid_port] = expr_key
	elif pop_t > 0.0:
		pop_t = maxf(0.0, pop_t - (1.0 / 60.0))
	_expr_pop_timer_by_id[fid_port] = pop_t

	var port_sz: float = 25.0 * ui_scale
	var base_port_rect: Rect2 = Rect2(rect.position.x + 4.0 * ui_scale, rect.position.y + 4.5 * ui_scale, port_sz, port_sz)
	var pop_grow: float = (pop_t / 0.16) * 2.2 * ui_scale
	var port_rect: Rect2 = base_port_rect.grow(pop_grow)
	canvas.draw_rect(port_rect, Color(0.14, 0.17, 0.24, 0.98), true)

	var drew_splash: bool = false
	var expr_port_path: String = "res://assets/portraits/agent_zero_expr_" + expr_key + ".png"
	var is_powered_hero_hud: bool = char_id in ["goku", "luffy", "naruto", "saitama", "solaria", "atlas", "shinobi", "tideweaver"]
	if reg != null and not is_powered_hero_hud:
		var ez_tex: Texture2D = reg.call("load_cached_texture", expr_port_path) as Texture2D
		if ez_tex != null:
			var hud_mod: Color = Color.WHITE
			if char_id not in ["johnny", "agent_zero"]:
				var h_tint_hud: float = fmod(float(abs(char_id.hash()) % 360), 360.0) / 360.0
				hud_mod = Color.from_hsv(h_tint_hud, 0.22, 1.04, 1.0)
			canvas.draw_texture_rect(ez_tex, port_rect.grow(-1.0), false, hud_mod)
			drew_splash = true
	if not drew_splash:
		var pcx: float = port_rect.position.x + port_rect.size.x * 0.5
		var pcy: float = port_rect.position.y + port_rect.size.y * 0.56
		var is_awk: bool = (fighter.get("awakening_timer") != null and float(fighter.get("awakening_timer")) > 0.0)
		var st_dict: Dictionary = _PreloadTacticalStrikerRigPainter.get_character_style(char_id, is_awk)
		var rv_node: Node = fighter.get("rig_view") as Node
		var full_expr: String = str(rv_node.call("get_current_expression_id")) if (rv_node != null and rv_node.has_method("get_current_expression_id")) else "CONFIDENT_SMIRK"
		canvas.draw_rect(Rect2(pcx - 7.5 * ui_scale, pcy + 3.0 * ui_scale, 15.0 * ui_scale, 8.0 * ui_scale), st_dict["jacket_lit"], true)
		canvas.draw_set_transform(Vector2(pcx, pcy - 1.5 * ui_scale), 0.0, Vector2(2.35 * ui_scale, 2.35 * ui_scale))
		_PreloadTacticalStrikerRigPainter._draw_sculpted_head_and_face(
			canvas,
			Vector2.ZERO,
			0.0,
			full_expr,
			false,
			st_dict,
			st_dict["skin_lit"],
			st_dict["skin_mid"],
			st_dict["hair_lit"],
			st_dict["hair_mid"],
			Color(0.06, 0.07, 0.11, 1.0),
			false,
			false,
			1.0
		)
		canvas.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	var expr_border_col: Color = Color(0.55, 0.62, 0.75, 0.95)
	if expr_key == "shout":
		expr_border_col = Color(1.0, 0.65, 0.22, 0.98)
	elif expr_key == "hurt":
		expr_border_col = Color(1.0, 0.25, 0.30, 0.98)
	elif expr_key == "victory":
		expr_border_col = Color(0.35, 0.96, 0.62, 0.98)
	canvas.draw_rect(port_rect, expr_border_col, false, 1.2)

	# 2. Right 4-slot Y8 Weapon Inventory Boxes ([1: Melee] [2: Gun] [3: Thrown] [4: Powerup], Screenshots 2 & 3)
	var slot_box_sz: float = 16.0 * ui_scale
	var slot_gap: float = 2.5 * ui_scale
	var total_slots_w: float = 4.0 * slot_box_sz + 3.0 * slot_gap
	var show_slots: bool = rect.size.x >= (port_sz + total_slots_w + 55.0 * ui_scale)
	var slots_start_x: float = rect.end.x - total_slots_w - 4.0 * ui_scale

	var inv_var: Variant = fighter.get("inventory")
	var ammo_var: Variant = fighter.get("inventory_ammo")
	var inv: Dictionary = inv_var as Dictionary if typeof(inv_var) == TYPE_DICTIONARY else {}
	var am: Dictionary = ammo_var as Dictionary if typeof(ammo_var) == TYPE_DICTIONARY else {}

	var slot_wids: Array[String] = ["", "", "", ""]
	var slot_ammos: Array[int] = [-1, 0, 0, -1]
	# Slot 1: Melee
	var m_wid: String = str(inv.get(1, "FISTS")).to_upper()
	if m_wid != "FISTS" and m_wid != "UNARMED":
		slot_wids[0] = m_wid
	# Slot 2: Ranged Gun (check slot 2 then slot 3 fallback)
	var g_wid: String = str(inv.get(2, "")).to_upper()
	var g_ammo: int = int(am.get(2, 0))
	if g_wid.is_empty() or g_ammo <= 0:
		g_wid = str(inv.get(3, "")).to_upper()
		g_ammo = int(am.get(3, 0))
	if not g_wid.is_empty() and g_ammo > 0:
		slot_wids[1] = g_wid
		slot_ammos[1] = g_ammo
	# Slot 3: Throwable (inventory key 4)
	var t_wid: String = str(inv.get(4, "")).to_upper()
	var t_ammo: int = int(am.get(4, 0))
	if not t_wid.is_empty() and t_ammo > 0:
		slot_wids[2] = t_wid
		slot_ammos[2] = t_ammo
	# Slot 4: Powerup (inventory key 5)
	var p_wid: String = str(inv.get(5, "")).to_upper()
	if not p_wid.is_empty():
		slot_wids[3] = p_wid

	if show_slots:
		for s_i: int in range(4):
			var sx: float = slots_start_x + float(s_i) * (slot_box_sz + slot_gap)
			var sy: float = rect.position.y + 4.0 * ui_scale
			var srect: Rect2 = Rect2(sx, sy, slot_box_sz, slot_box_sz)
			var swid: String = slot_wids[s_i]
			var has_item: bool = not swid.is_empty()
			canvas.draw_rect(srect, Color(0.32, 0.07, 0.07, 0.96) if not has_item else Color(0.42, 0.09, 0.09, 0.98), true)
			canvas.draw_rect(srect, Color(0.68, 0.16, 0.15, 0.95) if not has_item else Color(0.92, 0.32, 0.24, 0.98), false, 1.0)
			if has_item and reg != null:
				var swdata: Dictionary = reg.call("get_weapon_data", swid) as Dictionary
				var stex_path: String = str(swdata.get("pickup_texture", ""))
				if stex_path.is_empty():
					stex_path = str(swdata.get("dropped_texture", ""))
				var stex: Texture2D = reg.call("load_cached_texture", stex_path) as Texture2D
				if stex != null:
					var tsz: Vector2 = stex.get_size()
					var max_dim: float = maxf(1.0, maxf(tsz.x, tsz.y))
					var draw_sc: float = minf(1.2 * ui_scale, (slot_box_sz - 3.0 * ui_scale) / max_dim)
					var dsize: Vector2 = tsz * draw_sc
					var dpos: Vector2 = srect.position + (srect.size - dsize) * 0.5
					canvas.draw_texture_rect(stex, Rect2(dpos, dsize), false)
			# Draw 2-digit ammo count below Ranged Gun (s_i==1) & Throwable (s_i==2)
			if s_i in [1, 2] and has_item and slot_ammos[s_i] > 0:
				var am_str: String = "%02d" % slot_ammos[s_i]
				canvas.draw_string(
					font,
					Vector2(sx - 2.0, sy + slot_box_sz + 9.0 * ui_scale),
					am_str,
					HORIZONTAL_ALIGNMENT_CENTER,
					slot_box_sz + 4.0,
					int(7.5 * ui_scale),
					Color(0.96, 0.96, 0.98, 1.0)
				)

	# 3. Center Name + Green HP Bar ('lifebar') + White Stamina Bar ('energybar') + LoL Resource & 4 Skill Icons
	var bar_x: float = port_rect.end.x + 5.0 * ui_scale
	var right_limit_x: float = (slots_start_x - 5.0 * ui_scale) if show_slots else (rect.end.x - 5.0 * ui_scale)
	var bar_w: float = maxf(18.0, right_limit_x - bar_x)

	var dname: String = str(fighter.get("display_name")).to_upper()
	if dname.is_empty():
		dname = char_id.to_upper()
	var is_bot_f: bool = bool(fighter.get("is_bot"))
	var prefix: String = ("B" + str(idx + 1) + " ") if is_bot_f else ("P" + str(idx + 1) + " ")

	canvas.draw_string(
		font,
		Vector2(bar_x, rect.position.y + 9.5 * ui_scale),
		prefix + dname,
		HORIZONTAL_ALIGNMENT_LEFT,
		bar_w,
		int(7.0 * ui_scale),
		Color(0.96, 0.96, 0.98, 1.0)
	)

	var is_powered: bool = bool(fighter.get("is_powered_fighter"))
	var fid_card: int = fighter.get_instance_id()
	var trail_hp_card: float = float(_trailing_hp_by_id.get(fid_card, hp))
	if hp < trail_hp_card:
		trail_hp_card = maxf(hp, move_toward(trail_hp_card, hp, max_hp * 0.016))
	else:
		trail_hp_card = hp
	_trailing_hp_by_id[fid_card] = trail_hp_card
	var trail_ratio_card: float = clampf(trail_hp_card / max_hp, hp_ratio, 1.0)
	var hp_h: float = (5.0 if is_powered else 6.5) * ui_scale
	var hp_y: float = rect.position.y + (11.5 if is_powered else 14.0) * ui_scale
	canvas.draw_rect(Rect2(bar_x, hp_y, bar_w, hp_h), Color(0.18, 0.06, 0.06, 0.95), true)
	if trail_ratio_card > hp_ratio + 0.005:
		canvas.draw_rect(Rect2(bar_x, hp_y, bar_w * trail_ratio_card, hp_h), Color(1.0, 0.96, 0.9, 0.92), true)
	canvas.draw_rect(Rect2(bar_x, hp_y, bar_w * hp_ratio, hp_h), _get_hp_bar_color(hp_ratio), true)
	canvas.draw_rect(Rect2(bar_x, hp_y, bar_w, hp_h), Color(0.04, 0.04, 0.05, 0.9), false, 1.0)

	var st_h: float = (3.0 if is_powered else 4.0) * ui_scale
	var st_y: float = hp_y + hp_h + (1.5 if is_powered else 2.5) * ui_scale
	canvas.draw_rect(Rect2(bar_x, st_y, bar_w, st_h), Color(0.16, 0.17, 0.2, 0.95), true)
	canvas.draw_rect(Rect2(bar_x, st_y, bar_w * st_ratio, st_h), Color(0.95, 0.96, 0.98, 0.98), true)
	canvas.draw_rect(Rect2(bar_x, st_y, bar_w, st_h), Color(0.04, 0.04, 0.05, 0.9), false, 1.0)

	# 4. LoL Bespoke Resource Bar + 4 Skill Cooldown Icons (U I O P / 5 6 7 8) for Powered Fighters
	if is_powered:
		var r_val: float = float(fighter.get("resource_val")) if fighter.get("resource_val") != null else 0.0
		var r_max: float = maxf(1.0, float(fighter.get("resource_max")) if fighter.get("resource_max") != null else 100.0)
		var r_ratio: float = clampf(r_val / r_max, 0.0, 1.0)
		var r_spec: Dictionary = fighter.get("resource_spec") as Dictionary if typeof(fighter.get("resource_spec")) == TYPE_DICTIONARY else {}
		var r_col: Color = Color.from_string(str(r_spec.get("bar_color", "#FFCC22")), Color(1.0, 0.82, 0.22, 1.0))
		if float(fighter.get("overheat_timer")) > 0.0:
			r_col = Color(1.0, 0.22, 0.16, 1.0)
		var res_y: float = st_y + st_h + 1.5 * ui_scale
		var res_h: float = 4.0 * ui_scale
		var sk_strip_w: float = minf(bar_w * 0.48, 44.0 * ui_scale)
		var res_bar_w: float = maxf(16.0, bar_w - sk_strip_w - 3.0 * ui_scale)
		canvas.draw_rect(Rect2(bar_x, res_y, res_bar_w, res_h), Color(0.08, 0.09, 0.12, 0.96), true)
		canvas.draw_rect(Rect2(bar_x, res_y, res_bar_w * r_ratio, res_h), r_col, true)
		canvas.draw_rect(Rect2(bar_x, res_y, res_bar_w, res_h), Color(0.04, 0.04, 0.05, 0.92), false, 1.0)

		# 4 mini skill cooldown squares to the right of the LoL Resource Bar
		var cds: Dictionary = fighter.get("skill_cooldowns") as Dictionary if typeof(fighter.get("skill_cooldowns")) == TYPE_DICTIONARY else {}
		var mcds: Dictionary = fighter.get("skill_max_cooldowns") as Dictionary if typeof(fighter.get("skill_max_cooldowns")) == TYPE_DICTIONARY else {}
		var deny_timers: Dictionary = fighter.get("skill_deny_flash_timers") as Dictionary if typeof(fighter.get("skill_deny_flash_timers")) == TYPE_DICTIONARY else {}
		var key_labels: Array = ["U", "I", "O", "P"] if idx == 1 else ["5", "6", "7", "8"]
		var sk_sz: float = 8.5 * ui_scale
		var sk_x0: float = bar_x + res_bar_w + 3.0 * ui_scale
		var sk_y0: float = res_y - 2.5 * ui_scale
		for sk_i: int in range(4):
			var s_num: int = sk_i + 1
			var rem_cd: float = float(cds.get(s_num, 0.0))
			var max_cd: float = maxf(0.1, float(mcds.get(s_num, 1.0)))
			var deny_t: float = float(deny_timers.get(s_num, 0.0))
			var shake_dx: float = (sin(float(Time.get_ticks_msec()) * 0.06) * 1.8 * ui_scale) if deny_t > 0.0 else 0.0
			var sk_rect: Rect2 = Rect2(sk_x0 + float(sk_i) * (sk_sz + 1.5 * ui_scale) + shake_dx, sk_y0, sk_sz, sk_sz)
			var is_ready: bool = (rem_cd <= 0.01) and (fighter.call("can_cast_skill_slot", s_num) if fighter.has_method("can_cast_skill_slot") else true)
			var bg_col: Color = Color(r_col.r * 0.45, r_col.g * 0.45, r_col.b * 0.45, 0.96) if is_ready else Color(0.12, 0.13, 0.16, 0.96)
			if deny_t > 0.0:
				bg_col = Color(0.88, 0.14, 0.14, 0.98)
			canvas.draw_rect(sk_rect, bg_col, true)
			if rem_cd > 0.01:
				var cd_frac: float = clampf(rem_cd / max_cd, 0.0, 1.0)
				canvas.draw_rect(Rect2(sk_rect.position.x, sk_rect.position.y + sk_sz * (1.0 - cd_frac), sk_sz, sk_sz * cd_frac), Color(0.02, 0.02, 0.03, 0.82), true)
			var bdr_col: Color = Color(1.0, 0.25, 0.22, 1.0) if deny_t > 0.0 else (r_col if is_ready else Color(0.38, 0.4, 0.45, 0.85))
			canvas.draw_rect(sk_rect, bdr_col, false, 1.0)
			canvas.draw_string(font, Vector2(sk_rect.position.x, sk_rect.position.y + sk_sz - 1.0), key_labels[sk_i], HORIZONTAL_ALIGNMENT_CENTER, sk_sz, int(5.5 * ui_scale), Color.WHITE if (is_ready or deny_t > 0.0) else Color(0.65, 0.65, 0.7, 0.9))
