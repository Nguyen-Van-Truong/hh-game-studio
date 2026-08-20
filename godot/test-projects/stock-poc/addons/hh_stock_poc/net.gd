@tool
extends RefCounted

## Line-delimited JSON TCP helper. Bind 127.0.0.1 only. Does not log tokens.

var _server: TCPServer
var _peers: Array[StreamPeerTCP] = []
var _bufs: Dictionary = {}


func listen_loopback(port: int) -> int:
	close()
	_server = TCPServer.new()
	var err: Error = _server.listen(port, "127.0.0.1")
	if err != OK:
		_server = null
		return -1
	return _server.get_local_port()


func close() -> void:
	for peer: StreamPeerTCP in _peers:
		peer.disconnect_from_host()
	_peers.clear()
	_bufs.clear()
	if _server != null:
		_server.stop()
		_server = null


func poll_io() -> void:
	if _server == null:
		return
	while _server.is_connection_available():
		var peer: StreamPeerTCP = _server.take_connection()
		if peer == null:
			break
		_peers.append(peer)
		_bufs[peer] = PackedByteArray()
	var dead: Array[StreamPeerTCP] = []
	for peer: StreamPeerTCP in _peers:
		peer.poll()
		var st: int = int(peer.get_status())
		if st != int(StreamPeerTCP.STATUS_CONNECTED):
			dead.append(peer)
			continue
		var avail: int = peer.get_available_bytes()
		if avail <= 0:
			continue
		var got: Array = peer.get_partial_data(avail)
		if int(got[0]) != OK:
			continue
		var chunk: PackedByteArray = got[1]
		var buf: PackedByteArray = _bufs.get(peer, PackedByteArray())
		buf.append_array(chunk)
		_bufs[peer] = buf
	for peer: StreamPeerTCP in dead:
		_drop(peer)


func take_line() -> Dictionary:
	for peer: StreamPeerTCP in _peers:
		var buf: PackedByteArray = _bufs.get(peer, PackedByteArray())
		var nl: int = _find_nl(buf)
		if nl < 0:
			continue
		var raw: PackedByteArray = buf.slice(0, nl)
		_bufs[peer] = buf.slice(nl + 1)
		var line: String = raw.get_string_from_utf8().strip_edges()
		if line.is_empty():
			continue
		return {"peer": peer, "line": line}
	return {}


func send_line(peer: StreamPeerTCP, text: String) -> void:
	if peer == null:
		return
	if int(peer.get_status()) != int(StreamPeerTCP.STATUS_CONNECTED):
		return
	var payload: PackedByteArray = (text + "\n").to_utf8_buffer()
	peer.put_data(payload)


func _find_nl(buf: PackedByteArray) -> int:
	var i: int = 0
	while i < buf.size():
		if buf[i] == 10:
			return i
		i += 1
	return -1


func _drop(peer: StreamPeerTCP) -> void:
	_bufs.erase(peer)
	_peers.erase(peer)
	peer.disconnect_from_host()
