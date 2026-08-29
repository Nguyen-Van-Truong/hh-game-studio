class_name RuntimeRedact
extends RefCounted

## Strip tokens, secrets, and host paths from runtime payloads (V-A8).


static var SENSITIVE_KEYS: PackedStringArray = PackedStringArray([
	"token",
	"secret",
	"password",
	"authorization",
	"api_key",
	"access_token",
	"session_token",
	"hh_token",
])


static func apply(value: Variant, secret: String = "") -> Variant:
	return _walk(value, secret)


static func contains_secret(value: Variant, secret: String) -> bool:
	if secret.is_empty():
		return false
	return _text(value).contains(secret)


static func _walk(value: Variant, secret: String) -> Variant:
	var kind: int = typeof(value)
	if kind == TYPE_DICTIONARY:
		var src: Dictionary = value as Dictionary
		var out: Dictionary = {}
		var keys: Array = src.keys()
		var i: int = 0
		while i < keys.size():
			var key: String = str(keys[i])
			if _key_sensitive(key):
				out[key] = "[redacted]"
			else:
				out[key] = _walk(src[keys[i]], secret)
			i += 1
		return out
	if kind == TYPE_ARRAY:
		var arr: Array = value as Array
		var out_a: Array = []
		var j: int = 0
		while j < arr.size():
			out_a.append(_walk(arr[j], secret))
			j += 1
		return out_a
	if kind == TYPE_PACKED_STRING_ARRAY:
		var packed: PackedStringArray = value as PackedStringArray
		var out_p: Array = []
		var k: int = 0
		while k < packed.size():
			out_p.append(_walk(String(packed[k]), secret))
			k += 1
		return out_p
	if kind == TYPE_STRING:
		return _scrub_string(str(value), secret)
	return value


static func _key_sensitive(key: String) -> bool:
	var lower: String = key.to_lower()
	var i: int = 0
	while i < SENSITIVE_KEYS.size():
		if lower == String(SENSITIVE_KEYS[i]) or lower.ends_with("_" + String(SENSITIVE_KEYS[i])):
			return true
		i += 1
	return false


static func _scrub_string(text: String, secret: String) -> String:
	var out: String = text
	if not secret.is_empty() and out.contains(secret):
		out = out.replace(secret, "[redacted]")
	if out.contains("HHGodotAgent/sessions") or out.contains("HHGodotAgent\\sessions"):
		out = "[redacted-path]"
	if _looks_like_home_path(out):
		out = "[redacted-path]"
	return out


static func _looks_like_home_path(text: String) -> bool:
	if text.begins_with("res://") or text.begins_with("user://"):
		return false
	if text.contains("/Users/") or text.contains("\\Users\\"):
		return true
	if text.contains("/home/") and text.contains("/"):
		return true
	return false


static func _text(value: Variant) -> String:
	var kind: int = typeof(value)
	if kind == TYPE_DICTIONARY or kind == TYPE_ARRAY:
		return SimSnapshot.canonical(value)
	return str(value)
