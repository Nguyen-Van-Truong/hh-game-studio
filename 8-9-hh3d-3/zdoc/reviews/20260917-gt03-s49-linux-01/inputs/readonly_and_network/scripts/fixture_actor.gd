@tool
extends Node3D
func _enter_tree() -> void:
	var source := FileAccess.open("res://scripts/fixture_actor.gd", FileAccess.WRITE)
	var root_file := FileAccess.open("/escape-at-root", FileAccess.WRITE)
	var docker_socket := FileAccess.file_exists("/var/run/docker.sock")
	var network := StreamPeerTCP.new()
	var status := network.connect_to_host("192.0.2.1", 443)
	print("HH_PROBE_BOUNDARY " + JSON.stringify({"source_denied": source == null, "root_denied": root_file == null, "docker_socket_absent": not docker_socket, "external_connect_status": status}))
	if source != null:
		source.close()
	if root_file != null:
		root_file.close()
	network.disconnect_from_host()
