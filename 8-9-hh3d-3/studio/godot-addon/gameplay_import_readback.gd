extends SceneTree
## Trusted loader/importer readback for the gameplay source sandbox.
##
## This script is mounted read-only by the pinned executor.  It loads every
## admitted scene through ResourceLoader and decodes admitted binary assets
## with Godot's in-process GLTF/PNG codecs.  Headless Godot has no editor
## import cache, so asking ResourceLoader for GLB/PNG would emit a false
## "No loader found" error before the codec can prove the bytes are valid.
## The harness never instantiates a candidate scene or explicitly loads a
## candidate Script resource.  Parse/type checks for scripts remain separate.

const MAX_SCENES: int = 64
const ENTRYPOINT: String = "res://scenes/fixture.tscn"
const AVATAR: String = "res://assets/avatar.glb"
const SPRITE_SHEET: String = "res://assets/sprite_sheet.png"

var failures: Array[String] = []
var scene_count: int = 0
var asset_count: int = 0
var entrypoint_seen: bool = false

func _fail(reason: String) -> void:
	if failures.is_empty():
		printerr("HH_GAMEPLAY_IMPORT_REJECT " + reason)
	failures.append(reason)

func _load_scene(path: String) -> void:
	if scene_count >= MAX_SCENES:
		_fail("SCENE_CAP")
		return
	var scene: Resource = ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE)
	if scene == null or not scene is PackedScene:
		_fail("SCENE_LOAD_" + path)
		return
	scene_count += 1
	if path == ENTRYPOINT:
		entrypoint_seen = true

func _load_asset(path: String, type_hint: String) -> void:
	if not FileAccess.file_exists(path):
		return
	var raw: PackedByteArray = FileAccess.get_file_as_bytes(path)
	if raw.is_empty():
		_fail("ASSET_EMPTY_" + path)
		return
	if type_hint == "PackedScene":
		# GLTFDocument is the runtime equivalent of the GLB importer and does
		# not require a generated .godot/imported cache.
		var document := GLTFDocument.new()
		var state := GLTFState.new()
		var error: Error = document.append_from_buffer(raw, "", state)
		if error != OK:
			_fail("ASSET_GLTF_" + path)
	elif type_hint == "Texture2D":
		var image := Image.new()
		var error: Error = image.load_png_from_buffer(raw)
		if error != OK or image.is_empty():
			_fail("ASSET_PNG_" + path)
	asset_count += 1

func _initialize() -> void:
	var scenes: DirAccess = DirAccess.open("res://scenes")
	if scenes == null:
		_fail("SCENES_ROOT")
	else:
		var names: PackedStringArray = scenes.get_files()
		names.sort()
		for name: String in names:
			if name.ends_with(".tscn"):
				_load_scene("res://scenes/" + name)
		if not entrypoint_seen:
			_fail("ENTRYPOINT_MISSING")

	_load_asset(AVATAR, "PackedScene")
	_load_asset(SPRITE_SHEET, "Texture2D")
	var ok: bool = failures.is_empty()
	print("HH_GAMEPLAY_IMPORT_READBACK " + JSON.stringify({
		"schema": "hh-gameplay-import-readback-1",
		"scene_count": scene_count,
		"asset_count": asset_count,
		"entrypoint_seen": entrypoint_seen,
		"ok": ok
	}))
	quit(0 if ok else 46)
