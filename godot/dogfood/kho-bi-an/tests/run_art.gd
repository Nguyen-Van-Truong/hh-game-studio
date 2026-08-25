extends SceneTree

const MANIFEST_PATH: String = "res://assets/ASSET_MANIFEST.json"
const LAYOUT_PATH: String = "res://assets/ATLAS_LAYOUT.json"
const CONTACT_PATH: String = "res://assets/audit/contact_sheet.png"
const PREVIEW_USER: String = "user://kho_bi_an_r8wp3_anim_preview.png"
const AUDIO_USER: String = "user://kho_bi_an_r8wp3_audio_audit.json"

var _fails: PackedStringArray = PackedStringArray()
var _contact: String = "unproven"
var _anim: String = "unproven"
var _audio: String = "unproven"
var _attrib: String = "unproven"
var _license: String = "unproven"


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	_test_graybox_untouched()
	var manifest: Dictionary = _load_json(MANIFEST_PATH)
	var layout: Dictionary = _load_json(LAYOUT_PATH)
	if manifest.is_empty() or layout.is_empty():
		_emit()
		quit(1)
		return
	_test_attrib_license(manifest)
	_test_contact(manifest, layout)
	_test_animation(layout)
	_test_audio(manifest)
	_emit()
	quit(0 if _fails.is_empty() else 1)


func _test_graybox_untouched() -> void:
	var builder: WorldBuilder = WorldBuilder.new()
	var world: Node2D = builder.build()
	root.add_child(world)
	var layer: TileMapLayer = world.get_node_or_null("VaultRooms") as TileMapLayer
	if layer == null or layer.tile_set == null:
		_fail("live TileMapLayer missing")
	else:
		var atlas_src: TileSetSource = layer.tile_set.get_source(0)
		var atlas: TileSetAtlasSource = atlas_src as TileSetAtlasSource
		if atlas == null or atlas.texture == null:
			_fail("live tileset missing atlas")
		elif atlas.texture.resource_path != "res://assets/tiles/tileset_vault.png":
			_fail("live TileMapLayer must use tileset_vault.png")
	var state: GameState = GameState.new()
	if state.is_win():
		_fail("fresh GameState must not be win")
	state.has_key = true
	state.door_open = true
	if state.is_win() or state.relic_reached:
		_fail("key+door must not set relic_reached win")
	state.relic_reached = true
	if not state.is_win():
		_fail("relic_reached must remain the only win flag")


func _test_attrib_license(manifest: Dictionary) -> void:
	if bool(manifest.get("unknown_forbidden", false)) != true:
		_fail("ATTRIB release manifest must forbid UNKNOWN")
	if bool(manifest.get("placeholder_forbidden", false)) != true:
		_fail("ATTRIB release manifest must forbid PLACEHOLDER")
	var assets: Variant = manifest.get("assets", [])
	if not (assets is Array) or (assets as Array).is_empty():
		_fail("ATTRIB missing assets array")
		return
	var missing: int = 0
	var unknown: int = 0
	var bad_license: int = 0
	var i: int = 0
	var rows: Array = assets as Array
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		var asset_id: String = str(row.get("id", ""))
		if "PLACEHOLDER" in asset_id.to_upper() or "PLACEHOLDER" in str(row.get("rel", "")).to_upper():
			_fail("ATTRIB PLACEHOLDER id/path %s" % asset_id)
		var fields: PackedStringArray = PackedStringArray([
			"source", "tool", "prompt", "model", "license", "hash"
		])
		var f: int = 0
		while f < fields.size():
			if not row.has(String(fields[f])):
				_fail("ATTRIB missing %s on %s" % [String(fields[f]), asset_id])
				missing += 1
			f += 1
		var license: String = str(row.get("license", "")).strip_edges()
		if license == "" or license.to_upper() == "UNKNOWN":
			_fail("LICENSE UNKNOWN on %s" % asset_id)
			unknown += 1
		elif not _license_ok(license):
			_fail("LICENSE not commercial-safe on %s: %s" % [asset_id, license])
			bad_license += 1
		var rel_path: String = str(row.get("rel", ""))
		var kind: String = str(row.get("kind", ""))
		if kind == "bundled":
			var bundled_hash: String = str(row.get("hash", ""))
			if bundled_hash.length() == 64 and bundled_hash.to_lower() == bundled_hash:
				var hex_ok: bool = true
				var hi: int = 0
				while hi < bundled_hash.length():
					var ch: String = bundled_hash.substr(hi, 1)
					if not "0123456789abcdef".contains(ch):
						hex_ok = false
						break
					hi += 1
				if hex_ok:
					_fail("ATTRIB bundled %s must not claim SHA-256 of bytes" % asset_id)
			if rel_path != "":
				_fail("ATTRIB bundled %s must not claim a file of bytes" % asset_id)
		elif kind != "font" and rel_path != "":
			var res_path: String = str(row.get("path", ""))
			if not FileAccess.file_exists(res_path):
				_fail("ATTRIB missing file %s" % res_path)
			else:
				var got: String = _sha256(res_path)
				var expect: String = str(row.get("hash", ""))
				if got != expect:
					_fail("ATTRIB hash mismatch %s" % asset_id)
		i += 1
	if missing == 0 and _count_prefix("ATTRIB ") == 0:
		_attrib = "proven"
	if unknown == 0 and bad_license == 0 and _count_prefix("LICENSE ") == 0:
		_license = "proven"


func _test_contact(manifest: Dictionary, layout: Dictionary) -> void:
	if not FileAccess.file_exists(CONTACT_PATH):
		_fail("CONTACT missing %s" % CONTACT_PATH)
		return
	var imported: Texture2D = load(CONTACT_PATH) as Texture2D
	if imported == null:
		_fail("CONTACT could not import contact sheet")
		return
	var baked_img: Image = Image.new()
	if baked_img.load(CONTACT_PATH) != OK:
		_fail("CONTACT could not decode contact sheet PNG")
		return
	if baked_img.get_width() < 8 or baked_img.get_height() < 8:
		_fail("CONTACT sheet image empty")
		return
	var rebuilt: Image = _rebuild_contact(manifest, layout)
	if rebuilt == null:
		return
	if rebuilt.get_width() != baked_img.get_width() or rebuilt.get_height() != baked_img.get_height():
		_fail(
			"CONTACT size mismatch baked=%sx%s rebuilt=%sx%s"
			% [baked_img.get_width(), baked_img.get_height(), rebuilt.get_width(), rebuilt.get_height()]
		)
		return
	if not _images_equal(baked_img, rebuilt):
		_fail("CONTACT rebuilt sheet does not match imported pixels")
		return
	if _count_prefix("CONTACT ") == 0:
		_contact = "proven"


func _rebuild_contact(manifest: Dictionary, layout: Dictionary) -> Image:
	var by_id: Dictionary = {}
	var rows: Array = manifest.get("assets", []) as Array
	var i: int = 0
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		by_id[str(row.get("id", ""))] = row
		i += 1
	var slots: Array = layout.get("contact_slots", []) as Array
	if slots.size() < 8:
		_fail("CONTACT layout needs 8 slots")
		return null
	var pad: int = 6
	var cell_w: int = 70
	var cell_h: int = 56
	var cols: int = 4
	var rows_n: int = 2
	var sheet: Image = Image.create(pad * 2 + cols * cell_w, pad * 2 + rows_n * cell_h, false, Image.FORMAT_RGBA8)
	sheet.fill(Color8(18, 22, 42, 255))
	var s: int = 0
	while s < slots.size():
		var slot: Dictionary = slots[s] as Dictionary
		var asset_id: String = str(slot.get("id", ""))
		if not by_id.has(asset_id):
			_fail("CONTACT unknown slot %s" % asset_id)
			s += 1
			continue
		var row: Dictionary = by_id[asset_id] as Dictionary
		var res_path: String = str(row.get("path", ""))
		var tex: Texture2D = load(res_path) as Texture2D
		if tex == null:
			_fail("CONTACT cannot import %s" % asset_id)
			s += 1
			continue
		var src: Image = Image.new()
		if src.load(res_path) != OK:
			_fail("CONTACT no pixels %s" % asset_id)
			s += 1
			continue
		if src.get_format() != Image.FORMAT_RGBA8:
			src.convert(Image.FORMAT_RGBA8)
		var region: Array = slot.get("region", []) as Array
		var rx: int = int(region[0])
		var ry: int = int(region[1])
		var rw: int = int(region[2])
		var rh: int = int(region[3])
		var col: int = s % cols
		var row_i: int = int(s / cols)
		var dx: int = pad + col * cell_w + int((cell_w - rw) / 2)
		var dy: int = pad + row_i * cell_h + int((cell_h - rh) / 2)
		_blit_opaque(sheet, src, Rect2i(rx, ry, rw, rh), Vector2i(dx, dy))
		_stroke_rect(sheet, dx - 1, dy - 1, rw + 2, rh + 2, Color8(92, 68, 24, 255))
		s += 1
	return sheet


func _test_animation(layout: Dictionary) -> void:
	var actors: Dictionary = layout.get("actors", {}) as Dictionary
	var names: PackedStringArray = PackedStringArray(["actor_player", "actor_warden"])
	var preview: Image = Image.create(32 * 8 + 16, 32 * 2 + 12, false, Image.FORMAT_RGBA8)
	preview.fill(Color8(18, 22, 42, 255))
	var needed: PackedStringArray = PackedStringArray([
		"idle_down", "idle_left", "idle_right", "idle_up",
		"walk_down", "walk_left", "walk_right", "walk_up"
	])
	var a: int = 0
	while a < names.size():
		var actor_id: String = String(names[a])
		var path: String = str(actors.get(actor_id, ""))
		var tres_path: String = "res://assets/anim/%s.tres" % actor_id
		if not FileAccess.file_exists(tres_path):
			_fail("ANIM missing checked-in %s" % tres_path)
			a += 1
			continue
		var frames: SpriteFrames = load(tres_path) as SpriteFrames
		if frames == null:
			_fail("ANIM cannot load checked-in %s" % tres_path)
			a += 1
			continue
		var n: int = 0
		while n < needed.size():
			var clip: String = String(needed[n])
			if not frames.has_animation(clip):
				_fail("ANIM missing %s on %s" % [clip, actor_id])
			elif frames.get_frame_count(clip) < 2:
				_fail("ANIM %s/%s needs >=2 frames" % [actor_id, clip])
			n += 1
		var src: Image = Image.new()
		if src.load(path) != OK:
			_fail("ANIM cannot Image.load %s" % path)
			a += 1
			continue
		if src.get_format() != Image.FORMAT_RGBA8:
			src.convert(Image.FORMAT_RGBA8)
		_assert_walk_up_unique(actor_id, src)
		var f: int = 0
		while f < 4:
			preview.blit_rect(src, Rect2i((f + 2) * 32, 0, 32, 32), Vector2i(8 + f * 32, 6 + a * 32))
			f += 1
		a += 1
	var vfx: Dictionary = layout.get("vfx_interact", {}) as Dictionary
	var vfx_path: String = str(vfx.get("path", ""))
	var vfx_tres: String = "res://assets/anim/vfx_interact.tres"
	if not FileAccess.file_exists(vfx_tres):
		_fail("ANIM missing checked-in %s" % vfx_tres)
	else:
		var vfx_frames: SpriteFrames = load(vfx_tres) as SpriteFrames
		if vfx_frames == null:
			_fail("ANIM cannot load checked-in vfx")
		elif not vfx_frames.has_animation("burst"):
			_fail("ANIM vfx missing burst")
		elif vfx_frames.get_frame_count("burst") != 4:
			_fail("ANIM vfx burst needs 4 frames")
	var vfx_img: Image = Image.new()
	if vfx_img.load(vfx_path) != OK:
		_fail("ANIM vfx_interact missing")
	else:
		if vfx_img.get_format() != Image.FORMAT_RGBA8:
			vfx_img.convert(Image.FORMAT_RGBA8)
		preview.blit_rect(vfx_img, Rect2i(0, 0, 16, 16), Vector2i(8 + 4 * 32, 14))
	if not _preview_has_bible(preview):
		_fail("ANIM preview lacks bible cream/rust/teal")
	var save_preview: Error = preview.save_png(PREVIEW_USER)
	if save_preview != OK:
		_fail("ANIM could not write preview")
	if _count_prefix("ANIM ") == 0:
		_anim = "proven"
	print("HH_R8WP3_PREVIEW %s" % PREVIEW_USER)


func _assert_walk_up_unique(actor_id: String, src: Image) -> void:
	var idle: PackedStringArray = PackedStringArray()
	var c: int = 0
	while c < 2:
		idle.append(_crop_hash(src, c * 32, 3 * 32, 32, 32))
		c += 1
	var w: int = 2
	while w < 6:
		var walk_hash: String = _crop_hash(src, w * 32, 3 * 32, 32, 32)
		var i: int = 0
		while i < idle.size():
			if walk_hash == String(idle[i]):
				_fail("ANIM %s walk_up is byte-identical to idle_up" % actor_id)
				return
			i += 1
		w += 1


func _crop_hash(img: Image, x: int, y: int, w: int, h: int) -> String:
	var crop: Image = img.get_region(Rect2i(x, y, w, h))
	if crop.get_format() != Image.FORMAT_RGBA8:
		crop.convert(Image.FORMAT_RGBA8)
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(crop.get_data())
	return ctx.finish().hex_encode()


func _preview_has_bible(img: Image) -> bool:
	if img.get_format() != Image.FORMAT_RGBA8:
		img.convert(Image.FORMAT_RGBA8)
	var has_cream: bool = false
	var has_rust: bool = false
	var has_teal: bool = false
	var y: int = 0
	while y < img.get_height():
		var x: int = 0
		while x < img.get_width():
			var c: Color = img.get_pixel(x, y)
			if c.a < 0.99:
				x += 1
				continue
			var r: int = int(round(c.r * 255.0))
			var g: int = int(round(c.g * 255.0))
			var b: int = int(round(c.b * 255.0))
			if r == 237 and g == 228 and b == 200:
				has_cream = true
			elif r == 184 and g == 58 and b == 46:
				has_rust = true
			elif r == 61 and g == 139 and b == 122:
				has_teal = true
			x += 1
		y += 1
	return has_cream and has_rust and has_teal


func _test_audio(manifest: Dictionary) -> void:
	var needed: PackedStringArray = PackedStringArray([
		"sfx_pickup", "sfx_door", "sfx_caught", "sfx_win", "sfx_lose", "sfx_interact", "music_vault"
	])
	var buses: PackedStringArray = PackedStringArray(["Master", "Music", "SFX"])
	var b: int = 0
	while b < buses.size():
		if AudioServer.get_bus_index(String(buses[b])) < 0:
			_fail("AUDIO missing bus %s" % String(buses[b]))
		b += 1
	var by_id: Dictionary = {}
	var rows: Array = manifest.get("assets", []) as Array
	var i: int = 0
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		by_id[str(row.get("id", ""))] = row
		i += 1
	var report: Dictionary = {}
	var n: int = 0
	while n < needed.size():
		var asset_id: String = String(needed[n])
		if not by_id.has(asset_id):
			_fail("AUDIO missing manifest %s" % asset_id)
			n += 1
			continue
		var row: Dictionary = by_id[asset_id] as Dictionary
		var stream: AudioStream = load(str(row.get("path", ""))) as AudioStream
		if stream == null:
			_fail("AUDIO cannot import %s" % asset_id)
			n += 1
			continue
		var length: float = stream.get_length()
		if length <= 0.04:
			_fail("AUDIO %s too short" % asset_id)
		var wav: AudioStreamWAV = stream as AudioStreamWAV
		var peak: int = 0
		if wav != null:
			var data: PackedByteArray = wav.data
			if data.is_empty():
				_fail("AUDIO %s empty pcm" % asset_id)
			var p: int = 0
			while p + 1 < data.size():
				var sample: int = abs(data.decode_s16(p))
				if sample > peak:
					peak = sample
				p += 2
			if peak < 800:
				_fail("AUDIO %s silent" % asset_id)
			if asset_id == "music_vault":
				wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
		report[asset_id] = {
			"length": length,
			"peak": peak,
			"bus": str(row.get("bus", "")),
		}
		n += 1
	var json: String = JSON.stringify(report)
	var f: FileAccess = FileAccess.open(AUDIO_USER, FileAccess.WRITE)
	if f == null:
		_fail("AUDIO could not write audit")
	else:
		f.store_string(json)
		f.close()
	if _count_prefix("AUDIO ") == 0:
		_audio = "proven"
	print("HH_R8WP3_AUDIO %s" % AUDIO_USER)


func _load_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		_fail("missing %s" % path)
		return {}
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		_fail("cannot read %s" % path)
		return {}
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	f.close()
	if parsed is Dictionary:
		return parsed as Dictionary
	_fail("json not object %s" % path)
	return {}


func _sha256(path: String) -> String:
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		return ""
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(f.get_buffer(int(f.get_length())))
	f.close()
	return ctx.finish().hex_encode()


func _license_ok(license: String) -> bool:
	return (
		license == "original"
		or license == "CC0"
		or license == "MIT"
		or license == "OFL-1.1"
	)


func _images_equal(a: Image, b: Image) -> bool:
	if a.get_width() != b.get_width() or a.get_height() != b.get_height():
		return false
	if a.get_format() != Image.FORMAT_RGBA8:
		a.convert(Image.FORMAT_RGBA8)
	if b.get_format() != Image.FORMAT_RGBA8:
		b.convert(Image.FORMAT_RGBA8)
	var left: PackedByteArray = a.get_data()
	var right: PackedByteArray = b.get_data()
	if left.size() != right.size():
		return false
	var i: int = 0
	while i < left.size():
		if left[i] != right[i]:
			return false
		i += 1
	return true


func _blit_opaque(dest: Image, src: Image, region: Rect2i, to: Vector2i) -> void:
	var y: int = 0
	while y < region.size.y:
		var x: int = 0
		while x < region.size.x:
			var sx: int = region.position.x + x
			var sy: int = region.position.y + y
			if sx >= 0 and sy >= 0 and sx < src.get_width() and sy < src.get_height():
				var color: Color = src.get_pixel(sx, sy)
				if color.a > 0.001:
					var dx: int = to.x + x
					var dy: int = to.y + y
					if dx >= 0 and dy >= 0 and dx < dest.get_width() and dy < dest.get_height():
						dest.set_pixel(dx, dy, color)
			x += 1
		y += 1


func _stroke_rect(img: Image, x: int, y: int, w: int, h: int, color: Color) -> void:
	var xx: int = 0
	while xx < w:
		if x + xx >= 0 and x + xx < img.get_width():
			if y >= 0 and y < img.get_height():
				img.set_pixel(x + xx, y, color)
			if y + h - 1 >= 0 and y + h - 1 < img.get_height():
				img.set_pixel(x + xx, y + h - 1, color)
		xx += 1
	var yy: int = 0
	while yy < h:
		if y + yy >= 0 and y + yy < img.get_height():
			if x >= 0 and x < img.get_width():
				img.set_pixel(x, y + yy, color)
			if x + w - 1 >= 0 and x + w - 1 < img.get_width():
				img.set_pixel(x + w - 1, y + yy, color)
		yy += 1


func _fail(msg: String) -> void:
	_fails.append(msg)
	print("HH_ASSERT_FAIL %s" % msg)


func _count_prefix(prefix: String) -> int:
	var n: int = 0
	var i: int = 0
	while i < _fails.size():
		if String(_fails[i]).begins_with(prefix):
			n += 1
		i += 1
	return n


func _emit() -> void:
	print(
		"HH_R8WP3 CONTACT=%s ANIM=%s AUDIO=%s ATTRIB=%s LICENSE=%s"
		% [_contact, _anim, _audio, _attrib, _license]
	)
	if _fails.is_empty():
		print("PASS: R8-WP3 art/audio/license pipeline")
	else:
		print("FAIL: R8-WP3 art/audio/license pipeline")
		var i: int = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1
