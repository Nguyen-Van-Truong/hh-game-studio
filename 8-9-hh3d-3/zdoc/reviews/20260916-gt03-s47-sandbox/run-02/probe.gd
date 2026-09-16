@tool
extends EditorPlugin

func _enter_tree() -> void:
	if "--s47-probe" in OS.get_cmdline_user_args():
		call_deferred("_probe")

func _probe() -> void:
	var frames: int = 180
	while EditorInterface.get_edited_scene_root() == null and frames > 0:
		await get_tree().process_frame
		frames -= 1
	var root: Node = EditorInterface.get_edited_scene_root()
	var private_path: String = OS.get_environment("S47_PRIVATE_FILE")
	var private_root: String = OS.get_environment("S47_PRIVATE_ROOT")
	var read_file: FileAccess = FileAccess.open(private_path, FileAccess.READ)
	var read_error: int = FileAccess.get_open_error()
	if read_file != null:
		read_file.close()
	var write_file: FileAccess = FileAccess.open(private_path, FileAccess.WRITE)
	var write_error: int = FileAccess.get_open_error()
	if write_file != null:
		write_file.close()
	var directory: DirAccess = DirAccess.open(private_root)
	var directory_error: int = DirAccess.get_open_error()
	var project_write: FileAccess = FileAccess.open("res://forbidden-created.txt", FileAccess.WRITE)
	var project_write_error: int = FileAccess.get_open_error()
	if project_write != null:
		project_write.close()
	var control_file: FileAccess = FileAccess.open(OS.get_environment("S47_CONTROL_FILE"), FileAccess.WRITE)
	var control_ok: bool = control_file != null
	if control_file != null:
		control_file.store_string("S47_GRANTED_SCRATCH_OK")
		control_file.close()
	var version: Dictionary = Engine.get_version_info()
	var ok: bool = Engine.is_editor_hint() and DisplayServer.get_name() == "headless"
	ok = ok and root != null and root.name == "S47Fixture" and root.get_meta("hh_stable_id", "") == "s47.root"
	ok = ok and read_file == null and write_file == null and directory == null and project_write == null and control_ok
	ok = ok and version.get("major") == 4 and version.get("minor") == 7 and version.get("patch") == 2
	var result: Dictionary = {"schema":"S47_TRUSTED_SANDBOX_STARTUP_1", "ok":ok,
		"version":version, "editor_hint":Engine.is_editor_hint(), "display_server":DisplayServer.get_name(),
		"pid":OS.get_process_id(), "private_read_error":read_error, "private_write_error":write_error,
		"private_directory_error":directory_error, "readonly_project_write_error":project_write_error,
		"granted_scratch_write":control_ok, "trusted_probe_only":true, "hostile_script_safety":false}
	var output: FileAccess = FileAccess.open(OS.get_environment("S47_OUTPUT"), FileAccess.WRITE)
	if output == null:
		get_tree().quit(93)
		return
	output.store_string(JSON.stringify(result) + "\n")
	output.close()
	print("S47_TRUSTED_SANDBOX_STARTUP_COMPLETE " + str(ok))
	get_tree().quit(87 if ok else 92)
