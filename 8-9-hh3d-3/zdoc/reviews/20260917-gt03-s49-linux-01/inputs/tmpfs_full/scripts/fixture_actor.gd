@tool
extends Node3D
func _enter_tree() -> void:
	var chunk := PackedByteArray()
	chunk.resize(1024 * 1024)
	chunk.fill(65)
	var count := 0
	var bounded_error := false
	for index in range(24):
		var handle := FileAccess.open("/tmp/fill-%02d" % index, FileAccess.WRITE)
		if handle == null:
			bounded_error = true
			break
		handle.store_buffer(chunk)
		handle.flush()
		var error := handle.get_error()
		handle.close()
		if error != OK:
			bounded_error = true
			break
		count += 1
	print("HH_PROBE_TMPFS " + JSON.stringify({"full_files": count, "write_rejected": bounded_error}))
