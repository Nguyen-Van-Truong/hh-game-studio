# R1-WP3 MCP bake-off scorecard

Same scenario on disposable copies of **A** (satelliteoflove/godot-mcp `1b7d40537240fd54300f54bf6fda1ea91f06c878`) and **C** Beckett Lite `efb81dec03ba0af2b7a6dce0e4678bdbde5e454d`. Godot pin **4.7.1-stable**.

Tool count is **not** a score. Weights: correctness (5), self-verify (5), undo (4), security (4), maintainability (3), Godot 4.7.1 compatibility (3).

Driver: `tests/e2e/bakeoff/run_bakeoff.py`. Mode: headless. Eval/`godot_exec`/`call_method`/`Object.callv` were **disabled** for this spike. Session token required. Bind 127.0.0.1 only. `godot/plugin-project/` was not used.

## Scenario table

| Step | A | A evidence | A notes | C | C evidence | C notes |
|------|---|------------|---------|---|------------|---------|
| handshake_auth | PASS | {"id": "2", "result": {"addon_version": "4.1.0", "godot_version": "4.7.1-stable (official)", "p… | mcp_handshake ok; godot=4.7.1-stable (official) | PASS | {"id": 6, "jsonrpc": "2.0", "result": {"capabilities": {"prompts": {"listChanged": false}, "res… | initialize ok (Beckett — MCP for Godot (Lite)) |
| create_scene | FAIL | {"error": {"code": "UNKNOWN_COMMAND", "message": "Unknown command: create_scene"}, "id": "4", "… | no MCP create_scene; candidate documents agent-side .tscn write (not scored as PASS) | PASS | {"write": {"id": 8, "jsonrpc": "2.0", "result": {"content": [{"text": "wrote 61 bytes to res://… | write_file + open_scene (no dedicated create_scene; file tool is MCP) |
| open_scene | PASS | {"id": "5", "result": {"path": "res://main.tscn"}, "status": "success"} | open_scene res://main.tscn | PASS | {"id": 10, "jsonrpc": "2.0", "result": {"content": [{"text": "opened res://main.tscn", "type": … | open_scene res://main.tscn |
| save_scene | PASS | {"id": "6", "result": {"path": "res://main.tscn"}, "status": "success"} | save_scene | PASS | {"id": 11, "jsonrpc": "2.0", "result": {"content": [{"text": "saved scene", "type": "text"}, {"… | save_scene |
| add_node | FAIL | {"error": {"code": "UNKNOWN_COMMAND", "message": "Unknown command: add_node"}, "id": "7", "stat… | no live editor add_node (A is file-first for add/remove); typed=True | PASS | {"id": 12, "jsonrpc": "2.0", "result": {"content": [{"text": "created Node2D 'ChildA' under Roo… | create_node ChildA under Root |
| delete_node | FAIL | {"error": {"code": "UNKNOWN_COMMAND", "message": "Unknown command: delete_node"}, "id": "8", "s… | no live editor delete_node (A is file-first for add/remove); typed=True | PASS | {"id": 24, "jsonrpc": "2.0", "result": {"content": [{"text": "deleted node ChildACopy", "type":… | delete_node ChildACopy |
| duplicate_node | FAIL | {"error": {"code": "UNKNOWN_COMMAND", "message": "Unknown command: duplicate_node"}, "id": "9",… | no live editor duplicate_node (A is file-first for add/remove); typed=True | PASS | {"id": 14, "jsonrpc": "2.0", "result": {"content": [{"text": "duplicated ChildA as 'ChildACopy'… | duplicate_node ChildA |
| reparent_node | PASS | {"id": "14", "result": {"new_path": "Left/Right"}, "status": "success"} | reparent_node Right -> Left after disk-authored tree | PASS | {"id": 15, "jsonrpc": "2.0", "result": {"content": [{"text": "reparented ChildB under ChildA", … | reparent ChildB under ChildA |
| reorder_node | FAIL | {"error": {"code": "UNKNOWN_COMMAND", "message": "Unknown command: reorder_node"}, "id": "10", … | no live editor reorder_node (A is file-first for add/remove); typed=True | PASS | {"id": 16, "jsonrpc": "2.0", "result": {"content": [{"text": "moved ChildA to index 0", "type":… | move_node to_index=0 |
| set_property | PASS | {"set": {"id": "11", "result": {}, "status": "success"}, "get": {"id": "12", "result": {"proper… | update_node + get_node_properties readback | PASS | {"set": {"id": 17, "jsonrpc": "2.0", "result": {"content": [{"text": "set ChildA.position = (32… | set_property + describe_object readback |
| set_resource | PASS | {"set": {"id": "16", "result": {}, "status": "success"}, "mat": "\"():<CanvasItemMaterial#-9223… | update_node material + readback | PASS | {"id": 19, "jsonrpc": "2.0", "result": {"content": [{"text": "assigned CanvasItemMaterial to Ch… | set_resource inline CanvasItemMaterial |
| script_write | FAIL | {"error": {"code": "UNKNOWN_COMMAND", "message": "Unknown command: write_script"}, "id": "18", … | no MCP write_script; typed=True | PASS | {"id": 20, "jsonrpc": "2.0", "result": {"content": [{"text": "wrote 63 bytes to res://bakeoff_c… | write_script validate=true |
| script_validate | FAIL | {"error": {"code": "UNKNOWN_COMMAND", "message": "Unknown command: validate_script"}, "id": "19… | no MCP validate_script; typed=True | PASS | {"id": 21, "jsonrpc": "2.0", "result": {"content": [{"text": "OK \u2014 script compiles.", "typ… | validate_script |
| script_attach | FAIL | {"error": {"code": "UNKNOWN_COMMAND", "message": "Unknown command: attach_script"}, "id": "20",… | no MCP attach_script; typed=True | PASS | {"id": 22, "jsonrpc": "2.0", "result": {"content": [{"text": "attached res://bakeoff_child.gd t… | attach_script |
| undo | FAIL | {"error": {"code": "UNKNOWN_COMMAND", "message": "Unknown command: undo"}, "id": "21", "status"… | no MCP undo; typed=True | FAIL | {"undo": {"error": {"code": -32602, "message": "Unknown tool: undo"}, "id": 25, "jsonrpc": "2.0… | no MCP undo tool; scene mutations use EditorUndoRedoManager (human Ctrl+Z only). Agent-driven u… |
| redo | FAIL | {"error": {"code": "UNKNOWN_COMMAND", "message": "Unknown command: redo"}, "id": "22", "status"… | no MCP redo; typed=True | FAIL | {"error": {"code": -32602, "message": "Unknown tool: redo"}, "id": 26, "jsonrpc": "2.0"} | no MCP redo tool (UndoRedo-backed mutations, no agent redo) |
| play | PASS | {"id": "23", "result": {"frozen": true}, "status": "success"} | run_project frozen=true | PASS | {"id": 27, "jsonrpc": "2.0", "result": {"content": [{"text": "playing res://main.tscn", "type":… | play_scene main.tscn |
| stop | PASS | {"id": "27", "result": {}, "status": "success"} | stop_project | PASS | {"id": 35, "jsonrpc": "2.0", "result": {"content": [{"text": "stopped", "type": "text"}], "isEr… | stop_scene |
| log | PASS | {"id": "26", "result": {"cursor": 0, "match_count": 0, "messages": [], "returned_count": 0, "to… | get_log_messages | PASS | {"id": 31, "jsonrpc": "2.0", "result": {"content": [{"text": "[user://logs/godot.log] 1/1 lines… | logs_read |
| screenshot | SKIP | tests/e2e/bakeoff/evidence/A-game-small.png | 619-byte dummy gray PNG (not editor-visible) | SKIP | tests/e2e/bakeoff/evidence/C-game-small.png | 619-byte dummy gray PNG (not editor-visible) |
| runtime_state | FAIL | {"error": {"code": "TIMEOUT", "message": "Timed out waiting for get_runtime_state response"}, "… | runtime digest failed (game/debug session may be missing in headless) | PASS | {"tree": {"id": 32, "jsonrpc": "2.0", "result": {"content": [{"text": "{\"node_count\":3.0,\"tr… | get_remote_tree and/or runtime_get_property |
| select_focus | PASS | {"sel": {"id": "28", "result": {}, "status": "success"}, "got": {"id": "29", "result": {"select… | select_node + get_selected_nodes readback (headless: Inspector not shown to a human) | FAIL | {"create": {"id": 12, "jsonrpc": "2.0", "result": {"content": [{"text": "created Node2D 'ChildA… | dock/activity focus hint on create_node, but no EditorInterface.select tool so a human Inspecto… |
| retry_restart | PASS | {"id": "33", "result": {"restarting": true, "save": false}, "status": "success"} | restart_editor ACK (spike evidence, not a production ledger) | SKIP | {"error": {"code": -32602, "message": "Unknown tool: restart_editor"}, "id": 37, "jsonrpc": "2.… | no editor restart MCP tool on Lite (spike gap, not a ledger) |
| wrong_path | PASS | {"error": {"code": "FILE_NOT_FOUND", "message": "Scene file not found: res://no/such/scene.tscn… | missing scene is a typed error | PASS | {"id": 38, "jsonrpc": "2.0", "result": {"content": [{"text": "Error: No scene at: res://no/such… | missing scene is a typed/handler error |
| wrong_token | PASS | {"error": {"code": "AUTH_FAILED", "message": "missing or invalid session token"}, "id": "1", "s… | AUTH_FAILED (or typed error) on bad token | PASS | {"http_status": 401, "error": {"code": "HTTP_401", "message": "unauthorized"}} | 401/typed error on bad Bearer token |
| wrong_schema | PASS | {"error": {"code": "INVALID_PARAMS", "message": "properties is required"}, "id": "31", "status"… | missing properties is a typed error | PASS | {"id": 39, "jsonrpc": "2.0", "result": {"content": [{"text": "Error: Missing required parameter… | create_node without type failed |
| unsupported_eval_or_callv | PASS | {"error": {"code": "DISABLED", "message": "godot_exec/eval is disabled for the HH bake-off spik… | exec_run refused; godot_exec disabled for spike | PASS | {"id": 40, "jsonrpc": "2.0", "result": {"content": [{"text": "Error: DISABLED: call_method/Obje… | call_method/Object.callv refused; disabled for spike |

## Ranking (weighted criteria, not tool count)

| Criterion | Weight | A | C |
|-----------|--------|---|---|
| correctness | 5 | 1.92 | 5.0 |
| self_verify | 5 | 3.0 | 3.0 |
| undo | 4 | 0.0 | 0.0 |
| security | 4 | 5.0 | 5.0 |
| maintainability | 3 | 3.0 | 4.0 |
| godot_471 | 3 | 5.0 | 5.0 |
| **weighted total** | | **2.858** | **3.625** |

Row counts: A PASS 15 / FAIL 11 / SKIP 1; C PASS 22 / FAIL 3 / SKIP 2.

**Ranking: C** (higher weighted score). A lead, if any, is runtime/select. C lead, if any, is scene CRUD + script validate. Agent-driven undo/redo is FAIL for both (internal EditorUndoRedoManager is not scored).

## Maintainability notes

- **A maintainability (3/5):** Node sidecar + GDScript addon matches our intended sidecar/plugin split, but mutations are disk-first with **zero UndoRedo**, empty property-set success, fixed port 6550 (overridden only in this spike), and no session token upstream. npm/`npx -y` in the README is forbidden here (T5).

- **C maintainability (4/5):** GDScript-only, 4.7.1 CI, UndoRedo on scene tools, validate-before-write. Zero-sidecar **conflicts** with our chosen TypeScript sidecar architecture. `call_method`/`Object.callv` and a tokenless upgrade path are MUST-PATCH. Full itch SKUs are E2 — do not buy.

## MUST-PATCH leftover (G1 must not vendor as-is)

- **A:** session token + random port; disable `godot_exec`; EditorUndoRedoManager (or atomic file + conflict check); postcondition readback on `update_node`; export-strip MCPGameBridge autoload.
- **C Lite:** keep `call_method` off the OWNER_AUTOPILOT surface; require token even on upgrade; do not follow `npx mcp-remote`; never enable Full; wrap in our sidecar if G1 vendors anything.
- **Both:** G1 must not ship either as-is. Fallback remains writing `addons/hh_agent` + `bridge/` ourselves if these MUST-PATCH rows stay open.

## Security spike (this WP only)

- Disposable copies under `tests/e2e/bakeoff/work/` (gitignored).
- Token required; not written to this file.
- `godot_exec` / `call_method` disabled; a PASS on `unsupported_eval_or_callv` means **refused**.
- Human editor without MCP: `hh-godot-editor.bat`.
