//! Conformance generated from `gs_registry::all_methods()` (MASTER 12.1 / T0.6).

use std::io::Write;
use std::net::TcpStream;
use std::time::Duration;

use gs_protocol::{
    decode_message, read_ndjson_line, write_ndjson_line, Message, Request, PROTOCOL_VER,
};
use m0::{
    app_code, cid, entity_count, open_project, revision, spawn_named, start_bus,
    ui_only_method_names, APP_CODE_PROTO, CONFLICT, INVALID_PARAMS, INVALID_REQUEST,
    MAX_LINE_BYTES, UNAUTHORIZED,
};
use serde_json::json;

#[test]
fn agent_cannot_call_any_ui_only_method() {
    let (dir, bus) = start_bus();
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let names = ui_only_method_names();
    assert!(
        !names.is_empty(),
        "all_methods() must include UiOnly entries"
    );
    for name in names {
        let err = agent
            .call(name, json!({}))
            .expect_err(&format!("{name} must fail for agent"));
        assert_eq!(err.code, UNAUTHORIZED, "{name} code={}", err.code);
        assert_eq!(app_code(&err), "E_UNAUTHORIZED", "{name}");
    }
}

#[test]
fn invalid_params_missing_required_fields() {
    let (dir, bus) = start_bus();
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let missing_command_id = agent
        .call(
            "entity.spawn",
            json!({ "scene_id": "s_main", "name": "anon" }),
        )
        .expect_err("entity.spawn without command_id");
    assert_eq!(missing_command_id.code, INVALID_PARAMS);
    assert_eq!(app_code(&missing_command_id), "E_VALIDATION");

    let missing_id = agent
        .call("entity.rename", json!({ "command_id": cid(), "name": "x" }))
        .expect_err("entity.rename without id");
    assert!(
        missing_id.code == INVALID_PARAMS || app_code(&missing_id) == "E_VALIDATION",
        "rename missing id: code={} app={}",
        missing_id.code,
        app_code(&missing_id)
    );

    let missing_ids = agent
        .call("entity.destroy", json!({ "command_id": cid() }))
        .expect_err("entity.destroy without ids");
    assert_eq!(missing_ids.code, INVALID_PARAMS);

    let missing_commands = agent
        .call(
            "transaction.execute",
            json!({ "command_id": cid(), "label": "empty" }),
        )
        .expect_err("transaction.execute without commands");
    assert_eq!(missing_commands.code, INVALID_PARAMS);
}

#[test]
fn retry_same_command_id_after_spawn_is_idempotent() {
    let (dir, bus) = start_bus();
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let command_id = cid();
    let first = spawn_named(&mut agent, "once", &command_id);
    let retry = spawn_named(&mut agent, "once", &command_id);
    assert_eq!(first["spawned_ids"], retry["spawned_ids"]);
    assert_eq!(first["txn_id"], retry["txn_id"]);
    assert_eq!(entity_count(&mut agent), 1);
}

#[test]
fn expected_revision_mismatch_is_conflict() {
    let (dir, bus) = start_bus();
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    spawn_named(&mut agent, "keep", &cid());
    let err = agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": "stale",
                "expected_revision": "r-000999",
            }),
        )
        .expect_err("stale expected_revision");
    assert_eq!(err.code, CONFLICT);
    assert_eq!(app_code(&err), "E_CONFLICT");
    assert_eq!(entity_count(&mut agent), 1);
}

#[test]
fn txn_with_d_destroy_waits_for_ui_confirmation() {
    let (dir, bus) = start_bus();
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());

    let mut seed = Vec::new();
    for i in 0..21 {
        seed.push(json!({
            "method": "entity.spawn",
            "params": { "scene_id": "s_main", "name": format!("e{i}") },
        }));
    }
    let seeded = agent
        .call(
            "transaction.execute",
            json!({
                "label": "seed-21-spawns",
                "command_id": cid(),
                "commands": seed,
            }),
        )
        .expect("21 Base spawns are not D and apply immediately");
    let ids: Vec<String> = seeded["spawned_ids"]
        .as_array()
        .expect("spawned_ids")
        .iter()
        .map(|v| v.as_str().expect("id").to_owned())
        .collect();
    assert_eq!(ids.len(), 21);
    assert_eq!(entity_count(&mut agent), 21);

    let held = agent
        .call(
            "transaction.execute",
            json!({
                "label": "mass-destroy",
                "command_id": cid(),
                "commands": [{
                    "method": "entity.destroy",
                    "params": { "ids": ids },
                }],
            }),
        )
        .expect("D txn is held, not an RPC error");
    assert_eq!(held["status"], "pending_confirmation");
    let confirmation_id = held["confirmation_id"]
        .as_str()
        .expect("confirmation_id")
        .to_owned();
    assert_eq!(entity_count(&mut agent), 21, "held D txn must not apply");

    let approved = bus
        .ui()
        .call(
            "confirmation.approve",
            json!({ "confirmation_id": confirmation_id }),
        )
        .expect("human_ui approve");
    assert!(approved.get("revision").is_some());
    assert_eq!(entity_count(&mut agent), 0);

    let reuse = bus
        .ui()
        .call(
            "confirmation.approve",
            json!({ "confirmation_id": confirmation_id }),
        )
        .expect_err("confirmation_id is one-time");
    assert_eq!(app_code(&reuse), "E_NOT_FOUND");
}

#[test]
fn ndjson_line_over_4mb_is_e_proto() {
    let mut oversized = vec![b'x'; MAX_LINE_BYTES + 1];
    oversized.push(b'\n');
    let err = read_ndjson_line(&mut oversized.as_slice()).expect_err("over-cap line");
    assert_eq!(err.code(), Some(INVALID_REQUEST));
    assert_eq!(err.app_code(), Some(APP_CODE_PROTO));
}

#[test]
fn ndjson_line_over_4mb_via_tcp_other_agent_lives() {
    let (dir, bus) = start_bus();
    let mut survivor = bus.connect_agent("survivor").expect("hello survivor");
    open_project(&mut survivor, dir.path());
    spawn_named(&mut survivor, "keep", &cid());
    let before = revision(&mut survivor);

    let addr = bus.local_addr();
    let token = bus.endpoint().token();
    let mut stream = TcpStream::connect(addr).expect("connect oversized client");
    stream.set_nodelay(true).expect("nodelay");
    stream
        .set_read_timeout(Some(Duration::from_secs(30)))
        .expect("read timeout");
    stream
        .set_write_timeout(Some(Duration::from_secs(30)))
        .expect("write timeout");

    let hello = Request::new(
        1_i64,
        "session.hello",
        json!({
            "client_name": "oversized",
            "protocol_ver": PROTOCOL_VER,
            "token": token,
        }),
    );
    write_ndjson_line(&mut stream, &hello).expect("hello write");
    stream.flush().expect("hello flush");
    let mut reader = std::io::BufReader::new(stream.try_clone().expect("clone"));
    loop {
        let hello_line = read_ndjson_line(&mut reader).expect("hello response");
        match decode_message(&hello_line).expect("decode hello") {
            Message::Response(response) => {
                assert!(
                    response.error().is_none(),
                    "hello must succeed before the oversize probe"
                );
                break;
            }
            Message::Notification(_) => continue,
            other => panic!("expected hello response, got {other:?}"),
        }
    }

    let mut line = Vec::with_capacity(MAX_LINE_BYTES + 64);
    line.extend_from_slice(
        br#"{"jsonrpc":"2.0","id":99,"method":"session.ping","params":{"pad":""#,
    );
    line.resize(line.len() + MAX_LINE_BYTES, b'x');
    line.extend_from_slice(br#""}}"#);
    line.push(b'\n');
    let _ = stream.write_all(&line);
    let _ = stream.flush();

    let proto_line = read_ndjson_line(&mut reader).expect("E_PROTO response");
    match decode_message(&proto_line).expect("decode proto") {
        Message::Response(response) => {
            let err = response.error().expect("oversize must be an error");
            assert_eq!(err.code, INVALID_REQUEST);
            assert_eq!(
                err.data.as_ref().map(|d| d.app_code.as_str()),
                Some(APP_CODE_PROTO)
            );
        }
        other => panic!("expected error response, got {other:?}"),
    }

    let ping = survivor
        .call("session.ping", json!({}))
        .expect("survivor ping");
    assert_eq!(ping["ok"], true);
    assert_eq!(revision(&mut survivor), before);
    assert_eq!(entity_count(&mut survivor), 1);
}
