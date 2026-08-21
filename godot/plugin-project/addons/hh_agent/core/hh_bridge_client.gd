class_name HHAgentBridgeClient
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")

## Outbound WebSocket client. Godot masks client frames. Never logs the token.

var _ws: WebSocketPeer
var _host: String = ""
var _port: int = 0
var _project_id: String = ""
var _token: String = ""
var _hello_sent: bool = false
var _ready: bool = false
var _closed: bool = true
var _enqueue: Callable = Callable()
var _on_hello: Callable = Callable()
var _errors: HHAgentErrors = HHAgentErrors.new()


func set_enqueue(cb: Callable) -> void:
	_enqueue = cb


func set_hello_handler(cb: Callable) -> void:
	_on_hello = cb


func configure(host: String, port: int, project_id: String, token: String) -> void:
	_host = host
	_port = port
	_project_id = project_id
	_token = token


func start() -> Error:
	close()
	if _host != "127.0.0.1" or _port <= 0 or _project_id.is_empty() or not _token_ok(_token):
		return ERR_INVALID_PARAMETER
	_ws = WebSocketPeer.new()
	_ws.handshake_headers = PackedStringArray()
	var url: String = "ws://127.0.0.1:%d" % _port
	var err: Error = _ws.connect_to_url(url)
	if err != OK:
		_ws = null
		return err
	_closed = false
	_hello_sent = false
	_ready = false
	return OK


func poll() -> void:
	if _ws == null or _closed:
		return
	_ws.poll()
	var state: WebSocketPeer.State = _ws.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		if not _hello_sent:
			_send_hello()
		while _ws.get_available_packet_count() > 0:
			var pkt: PackedByteArray = _ws.get_packet()
			_on_text(pkt.get_string_from_utf8())
		return
	if state == WebSocketPeer.STATE_CLOSING:
		return
	if state == WebSocketPeer.STATE_CLOSED:
		_ready = false
		_closed = true
		_ws = null


func send_dict(payload: Dictionary) -> void:
	if _ws == null or not _ready:
		return
	var err: Error = _ws.send_text(JSON.stringify(payload))
	if err != OK:
		push_warning("hh_agent: send failed")


func is_ready() -> bool:
	return _ready and not _closed


func is_closed() -> bool:
	return _closed


func host() -> String:
	return _host


func port() -> int:
	return _port


func project_id() -> String:
	return _project_id


func close() -> void:
	_ready = false
	_hello_sent = false
	_closed = true
	if _ws != null:
		_ws.close()
		_ws = null


func has_configured_token() -> bool:
	return _token_ok(_token)


func _token_ok(token: String) -> bool:
	if token.length() != 64:
		return false
	var i: int = 0
	while i < 64:
		var code: int = token.unicode_at(i)
		var hex: bool = (
			(code >= 48 and code <= 57)
			or (code >= 97 and code <= 102)
			or (code >= 65 and code <= 70)
		)
		if not hex:
			return false
		i += 1
	return true


func _send_hello() -> void:
	var hello: Dictionary = {
		"type": HHAgentConstants.HELLO_TYPE,
		"protocol": HHAgentConstants.PROTOCOL,
		"project_id": _project_id,
		"token": _token,
	}
	var err: Error = _ws.send_text(JSON.stringify(hello))
	if err != OK:
		close()
		return
	_hello_sent = true


func _on_text(text: String) -> void:
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	var rec: Dictionary = parsed
	var kind: String = str(rec.get("type", ""))
	if kind == HHAgentConstants.HELLO_OK:
		_ready = rec.get("ok", false) == true
		if _on_hello.is_valid():
			_on_hello.call(_ready)
		return
	if kind == HHAgentConstants.HELLO_ERR:
		_ready = false
		if _on_hello.is_valid():
			_on_hello.call(false)
		close()
		return
	if kind == HHAgentConstants.PING_TYPE:
		send_dict({"type": HHAgentConstants.PONG_TYPE})
		return
	if kind == HHAgentConstants.REQUEST_TYPE:
		_offer_request(rec)
		return


func _offer_request(rec: Dictionary) -> void:
	if not _enqueue.is_valid():
		return
	var envelope_v: Variant = rec.get("envelope", {})
	var accepted: Variant = _enqueue.call(envelope_v if envelope_v is Dictionary else rec)
	if accepted == true:
		return
	var command_id: String = ""
	if envelope_v is Dictionary:
		command_id = str((envelope_v as Dictionary).get("command_id", ""))
	send_dict(_errors.fail(command_id, HHAgentErrors.E_BUSY, "inbound queue full", ""))
