extends RefCounted
## Independent RFC 8785 serializer for already validated JSON values.
## This is NOT a wire parser: Godot JSON.parse accepts non-JSON syntax and
## overwrites duplicate keys. An adapter must validate the original wire first.
## References: https://www.rfc-editor.org/rfc/rfc8785.html sections 3.2 and B.
## Binary64 rendering uses exact integer decimal expansion and midpoint bounds,
## not Godot's JSON.stringify/String.to_float or a Python/Node subprocess.

const SAFE_INTEGER: int = 9007199254740991
const LIMB_BASE: int = 1000000000
const MAX_DEPTH: int = 32
const MAX_ITEMS: int = 256
const MAX_STRING: int = 16384
const MAX_BYTES: int = 1048576

var error_code: String = ""


class ScalarString extends RefCounted:
	# Native Godot String cannot preserve U+0000. Keep Unicode scalar values
	# explicitly; the canonical output escapes NUL as the six ASCII chars.
	var points: Array[int]

	func _init(value: Array[int]) -> void:
		points = value.duplicate()


class ObjectPairs extends RefCounted:
	# Keys can include U+0000 too, so a native Dictionary is insufficient.
	var members: Array[Array]

	func _init(value: Array[Array]) -> void:
		members = value.duplicate()


func canonicalize(value: Variant) -> Dictionary:
	error_code = ""
	var output: String = _encode(value, 0)
	if not error_code.is_empty():
		return {"ok": false, "error": error_code}
	var bytes: PackedByteArray = output.to_utf8_buffer()
	if bytes.size() > MAX_BYTES:
		return {"ok": false, "error": "MESSAGE_TOO_LARGE"}
	return {"ok": true, "canonical": output, "utf8_hex": bytes.hex_encode(),
		"sha256": "sha256:" + output.sha256_text()}


func _fail(code: String) -> String:
	if error_code.is_empty():
		error_code = code
	return ""


func _encode(value: Variant, depth: int) -> String:
	if not error_code.is_empty():
		return ""
	if depth > MAX_DEPTH:
		return _fail("DEPTH_LIMIT")
	match typeof(value):
		TYPE_NIL:
			return "null"
		TYPE_BOOL:
			return "true" if value else "false"
		TYPE_INT:
			if value < -SAFE_INTEGER or value > SAFE_INTEGER:
				return _fail("INTEGER_REQUIRES_DECIMAL_STRING")
			return str(value)
		TYPE_FLOAT:
			return _number(value)
		TYPE_STRING:
			return _quote(value)
		TYPE_OBJECT:
			if value is ScalarString:
				return _quote_points(value.points)
			if value is ObjectPairs:
				return _encode_pairs(value.members, depth)
			return _fail("INVALID_TYPE")
		TYPE_ARRAY:
			if value.size() > MAX_ITEMS:
				return _fail("ARRAY_ITEM_LIMIT")
			var items: PackedStringArray = []
			for child: Variant in value:
				items.append(_encode(child, depth + 1))
			return "[" + ",".join(items) + "]"
		TYPE_DICTIONARY:
			if value.size() > MAX_ITEMS:
				return _fail("OBJECT_MEMBER_LIMIT")
			var names: Array[String] = []
			for key: Variant in value:
				if typeof(key) != TYPE_STRING:
					return _fail("INVALID_KEY")
				names.append(key)
			names.sort_custom(_utf16_less)
			var members: PackedStringArray = []
			for key: String in names:
				members.append(_quote(key) + ":" + _encode(value[key], depth + 1))
			return "{" + ",".join(members) + "}"
		_:
			return _fail("INVALID_TYPE")


func _quote(value: String) -> String:
	var points: Array[int] = []
	for index: int in value.length():
		points.append(value.unicode_at(index))
	return _quote_points(points)


func _quote_points(points: Array[int]) -> String:
	if points.size() > MAX_STRING:
		return _fail("STRING_LIMIT")
	var output: String = '"'
	for cp: int in points:
		if cp < 0 or cp > 0x10ffff or (cp >= 0xd800 and cp <= 0xdfff):
			return _fail("INVALID_UNICODE")
		match cp:
			8: output += "\\b"
			9: output += "\\t"
			10: output += "\\n"
			12: output += "\\f"
			13: output += "\\r"
			34: output += '\\"'
			92: output += "\\\\"
			_:
				output += "\\u%04x" % cp if cp < 32 else String.chr(cp)
	return output + '"'


func _encode_pairs(pairs: Array[Array], depth: int) -> String:
	if pairs.size() > MAX_ITEMS:
		return _fail("OBJECT_MEMBER_LIMIT")
	var entries: Array[Dictionary] = []
	var seen: Dictionary = {}
	for pair: Array in pairs:
		if pair.size() != 2 or not pair[0] is ScalarString:
			return _fail("INVALID_KEY")
		var key: ScalarString = pair[0]
		var quoted: String = _quote_points(key.points)
		if not error_code.is_empty():
			return ""
		if seen.has(quoted):
			return _fail("DUPLICATE_KEY")
		seen[quoted] = true
		entries.append({"quoted": quoted, "points": _points_utf16(key.points), "value": pair[1]})
	entries.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return _units_less(a.points, b.points))
	var members: PackedStringArray = []
	for entry: Dictionary in entries:
		members.append(str(entry.quoted) + ":" + _encode(entry.value, depth + 1))
	return "{" + ",".join(members) + "}"


func _utf16_units(value: String) -> Array[int]:
	var points: Array[int] = []
	for index: int in value.length():
		points.append(value.unicode_at(index))
	return _points_utf16(points)


func _points_utf16(points: Array[int]) -> Array[int]:
	var result: Array[int] = []
	for original: int in points:
		var cp: int = original
		if cp < 0x10000:
			result.append(cp)
		else:
			cp -= 0x10000
			result.append(0xd800 + (cp >> 10))
			result.append(0xdc00 + (cp & 0x3ff))
	return result


func _utf16_less(left: String, right: String) -> bool:
	var a: Array[int] = _utf16_units(left)
	var b: Array[int] = _utf16_units(right)
	return _units_less(a, b)


func _units_less(a: Array[int], b: Array[int]) -> bool:
	for index: int in mini(a.size(), b.size()):
		if a[index] != b[index]:
			return a[index] < b[index]
	return a.size() < b.size()


@warning_ignore("integer_division")
func _multiply(limbs: Array[int], factor: int) -> void:
	var carry: int = 0
	for index: int in limbs.size():
		var product: int = limbs[index] * factor + carry
		limbs[index] = product % LIMB_BASE
		carry = product / LIMB_BASE
	while carry > 0:
		limbs.append(carry % LIMB_BASE)
		carry /= LIMB_BASE


@warning_ignore("integer_division")
func _exact_decimal(mantissa: int, exponent: int) -> Dictionary:
	# value = mantissa * 2^exponent; negative exponents become 5^n / 10^n.
	# Limbs/factors stay below 1e9: every product fits in signed int64.
	var limbs: Array[int] = []
	while mantissa > 0:
		limbs.append(mantissa % LIMB_BASE)
		mantissa /= LIMB_BASE
	var remaining: int = absi(exponent)
	var chunk: int = 29 if exponent >= 0 else 12
	var factor: int = 536870912 if exponent >= 0 else 244140625
	while remaining >= chunk:
		_multiply(limbs, factor)
		remaining -= chunk
	for unused: int in remaining:
		_multiply(limbs, 2 if exponent >= 0 else 5)
	var digits: String = str(limbs[-1])
	for index: int in range(limbs.size() - 2, -1, -1):
		digits += "%09d" % limbs[index]
	return {"digits": digits, "point": digits.length() + mini(exponent, 0)}


func _compare_decimal(left: Dictionary, right: Dictionary) -> int:
	var lp: int = left.point
	var rp: int = right.point
	if lp != rp:
		return -1 if lp < rp else 1
	var a: String = left.digits
	var b: String = right.digits
	var width: int = maxi(a.length(), b.length())
	a += "0".repeat(width - a.length())
	b += "0".repeat(width - b.length())
	if a == b:
		return 0
	return -1 if a < b else 1


func _rounded(exact: Dictionary, count: int) -> Dictionary:
	var digits: String = exact.digits
	var point: int = exact.point
	if digits.length() <= count:
		return exact
	var prefix: String = digits.left(count)
	var tail: String = digits.substr(count)
	var half: String = "5" + "0".repeat(tail.length() - 1)
	# Closest decimal; exact half chooses the even final decimal digit.
	if tail > half or (tail == half and int(prefix[-1]) % 2 == 1):
		prefix = str(int(prefix) + 1)
		if prefix.length() > count:
			point += 1
	return {"digits": prefix, "point": point}


func _render_decimal(value: Dictionary) -> String:
	var digits: String = value.digits
	var point: int = value.point
	while digits.length() > 1 and digits.ends_with("0"):
		digits = digits.left(-1)
	if point > 0 and point <= 21:
		if digits.length() <= point:
			return digits + "0".repeat(point - digits.length())
		return digits.left(point) + "." + digits.substr(point)
	if point <= 0 and point > -6:
		return "0." + "0".repeat(-point) + digits
	var scientific: String = digits[0]
	if digits.length() > 1:
		scientific += "." + digits.substr(1)
	var exponent: int = point - 1
	return scientific + "e" + ("+" if exponent >= 0 else "") + str(exponent)


func _number(value: float) -> String:
	if not is_finite(value):
		return _fail("INVALID_NUMBER")
	if value == 0.0:
		return "0"
	var bytes: PackedByteArray = []
	bytes.resize(8)
	bytes.encode_double(0, absf(value))
	var bits: int = bytes.decode_u64(0)
	var biased: int = (bits >> 52) & 0x7ff
	var mantissa: int = bits & 0xfffffffffffff
	var exponent: int = -1074
	if biased != 0:
		mantissa += 0x10000000000000
		exponent = biased - 1075
	var exact: Dictionary = _exact_decimal(mantissa, exponent)
	var lower: Dictionary
	# Spacing below a normal power of two is half the spacing above it.
	if mantissa == 0x10000000000000 and biased > 1:
		lower = _exact_decimal(4 * mantissa - 1, exponent - 2)
	else:
		lower = _exact_decimal(2 * mantissa - 1, exponent - 1)
	var upper: Dictionary = _exact_decimal(2 * mantissa + 1, exponent - 1)
	var inclusive: bool = mantissa % 2 == 0
	for count: int in range(1, 18):
		var candidates: Array[Dictionary] = [_rounded(exact, count)]
		# At powers of two the interval is asymmetric. The nearest decimal can
		# miss the narrow side while its other neighbour fits the wider side.
		var digits: String = exact.digits
		if digits.length() > count:
			var prefix: int = int(digits.left(count))
			for coefficient: int in [prefix, prefix + 1]:
				var text: String = str(coefficient)
				candidates.append({"digits": text,
					"point": int(exact.point) + text.length() - count})
		for candidate: Dictionary in candidates:
			var above_lower: int = _compare_decimal(candidate, lower)
			var below_upper: int = _compare_decimal(candidate, upper)
			if (above_lower > 0 or (inclusive and above_lower == 0)) and \
					(below_upper < 0 or (inclusive and below_upper == 0)):
				return ("-" if value < 0.0 else "") + _render_decimal(candidate)
	return _fail("UNSUPPORTED_BINARY64_CONVERSION")
