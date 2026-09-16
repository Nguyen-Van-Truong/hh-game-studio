extends SceneTree
## Trusted golden-fixture runner only; no command application or wire admission.

const JCS = preload("res://jcs_godot.gd")


func _initialize() -> void:
	var parser: JSON = JSON.new()
	if parser.parse(FileAccess.get_file_as_string("res://vectors.json")) != OK:
		quit(2)
		return
	var data: Dictionary = parser.data
	var serializer: JCS = JCS.new()
	var rows: Array[Dictionary] = []
	for entry: Dictionary in data.cases:
		var row: Dictionary = serializer.canonicalize(_decode_fixture(entry.input))
		row["id"] = entry.id
		rows.append(row)
		if entry.has("request_body"):
			row = serializer.canonicalize(_decode_fixture(entry.request_body))
			row["id"] = str(entry.id) + ":request"
			rows.append(row)
	for entry: Dictionary in data.get("binary64", []):
		var bytes: PackedByteArray = str(entry.bits).hex_decode()
		bytes.reverse()
		var row: Dictionary = serializer.canonicalize(bytes.decode_double(0))
		row["id"] = entry.id
		rows.append(row)
	var rejected: Dictionary = {}
	for pair: Array in [["nan", NAN], ["infinity", INF], ["negative_infinity", -INF],
			["unsafe_integer", 9007199254740992], ["invalid_key", {1: "value"}],
			["surrogate", JCS.ScalarString.new([0xd800])],
			["invalid_scalar", JCS.ScalarString.new([0x110000])],
			["invalid_type", Vector2.ZERO], ["long_string", "a".repeat(16385)]]:
		rejected[pair[0]] = serializer.canonicalize(pair[1])
	print("HH_GT02_JCS " + JSON.stringify({"rows": rows, "rejected": rejected}))
	quit(0)


func _decode_fixture(node: Array) -> Variant:
	# The host encodes the original fixture value as a tagged tree, with exact
	# binary64 bytes and scalar codepoints. No expected canonical text is sent.
	# This avoids Godot JSON.parse's NUL replacement and decimal parsing drift.
	match node[0]:
		"null":
			return null
		"boolean":
			return node[1]
		"integer":
			return int(node[1])
		"binary64":
			var bytes: PackedByteArray = str(node[1]).hex_decode()
			bytes.reverse()
			return bytes.decode_double(0)
		"string":
			var points: Array[int] = []
			for value: float in node[1]:
				points.append(int(value))
			return JCS.ScalarString.new(points)
		"array":
			var array: Array = []
			for value: Array in node[1]:
				array.append(_decode_fixture(value))
			return array
		"object":
			var members: Array[Array] = []
			for value: Array in node[1]:
				members.append([_decode_fixture(value[0]), _decode_fixture(value[1])])
			return JCS.ObjectPairs.new(members)
	push_error("INVALID_TRUSTED_FIXTURE")
	return null
