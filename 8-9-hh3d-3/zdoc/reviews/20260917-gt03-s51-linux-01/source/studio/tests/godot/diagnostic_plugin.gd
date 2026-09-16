@tool
extends "res://addons/hh_studio/plugin.gd"
## Trusted fixture-only driver; this file is not installed as the product plugin.

const Probe = preload("res://tests/editor_probe.gd")


func _enter_tree() -> void:
	super._enter_tree()
	if "--hh-studio-editor-probe" in OS.get_cmdline_user_args():
		call_deferred("_run_probe")


func _run_probe() -> void:
	var probe := Probe.new()
	await probe.run(self)
