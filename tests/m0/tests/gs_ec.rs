//! Gap-filling GS-EC cases that are not already covered as the primary test.

use gs_scene::{Command, DispatchRequest, Error, DEFAULT_SCENE_ID};
use m0::{
    app_code, cid, entity_count, open_project, open_session, revision, spawn_named, spawn_session,
    start_bus, CONFLICT,
};
use serde_json::json;

#[test]
fn property_undo_n_spawns_restores_canonical_bytes() {
    use std::collections::BTreeMap;

    let (_dir, mut s) = open_session();
    let original = s.canonical_scene_bytes();
    const N: usize = 20;
    let mut commands = Vec::with_capacity(N);
    for i in 0..N {
        let mut comps = BTreeMap::new();
        comps.insert(
            "Transform2D".into(),
            json!({
                "x": (i as f64) * 0.5,
                "y": (i as f64) * -0.25,
                "rot": 0.0,
                "sx": 1.0,
                "sy": 1.0,
                "z_index": i as i32,
            }),
        );
        commands.push(Command::entity_spawn(
            DEFAULT_SCENE_ID,
            Some(format!("p{i}_{}", (i * 17) % 97)),
            None,
            comps,
        ));
    }
    s.dispatch(DispatchRequest::transaction(cid(), "act_01", commands))
        .expect("N spawns");
    assert_eq!(s.document().entity_count(), N);
    s.undo_last(&cid(), "act_01")
        .expect("undo_last inverts the txn");
    assert_eq!(
        s.canonical_scene_bytes(),
        original,
        "undo_last of the N-spawn txn must restore canonical scene bytes"
    );
    assert_eq!(s.document().entity_count(), 0);

    let (dir, bus) = start_bus();
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let mut seed = Vec::new();
    for i in 0..N {
        seed.push(json!({
            "method": "entity.spawn",
            "params": { "scene_id": "s_main", "name": format!("u{i}") },
        }));
    }
    agent
        .call(
            "transaction.execute",
            json!({ "command_id": cid(), "commands": seed }),
        )
        .expect("agent N-spawn txn");
    assert_eq!(entity_count(&mut agent), N);
    bus.ui()
        .call("undo.perform", json!({ "steps": 1 }))
        .expect("human_ui undo_last");
    assert_eq!(entity_count(&mut agent), 0);
}

#[test]
fn id_not_found_is_e_not_found_and_txn_rolls_back() {
    let (_dir, mut s) = open_session();
    let missing = "e_000042";
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::entity_rename(missing, "ghost"),
        ))
        .unwrap_err();
    assert!(
        matches!(err, Error::NotFound(ref id) if id == missing),
        "got {err:?}"
    );

    let before = s.canonical_scene_bytes();
    let err = s
        .dispatch(DispatchRequest::transaction(
            cid(),
            "act_01",
            vec![
                Command::entity_spawn(
                    DEFAULT_SCENE_ID,
                    Some("will-roll-back".into()),
                    None,
                    Default::default(),
                ),
                Command::entity_destroy(vec![missing.to_owned()]),
            ],
        ))
        .unwrap_err();
    assert!(matches!(err, Error::NotFound(_)), "got {err:?}");
    assert_eq!(s.document().entity_count(), 0);
    assert_eq!(s.canonical_scene_bytes(), before);

    let (dir, bus) = start_bus();
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    let err = agent
        .call(
            "entity.rename",
            json!({
                "command_id": cid(),
                "id": missing,
                "name": "ghost",
            }),
        )
        .expect_err("missing id over bus");
    assert_eq!(app_code(&err), "E_NOT_FOUND");
}

#[test]
fn two_agents_same_field_expected_revision_conflicts() {
    let (dir, bus) = start_bus();
    let mut a = bus.connect_agent("alpha").expect("hello a");
    let mut b = bus.connect_agent("beta").expect("hello b");
    assert_ne!(a.actor_id(), b.actor_id());
    open_project(&mut a, dir.path());

    let spawned = spawn_named(&mut a, "shared", &cid());
    let id = spawned["spawned_ids"][0].as_str().expect("id").to_owned();
    let base = revision(&mut a);

    b.call(
        "component.set",
        json!({
            "command_id": cid(),
            "id": id,
            "type": "Transform2D",
            "patch": { "x": 3.0, "y": 4.0 },
        }),
    )
    .expect("agent b writes first");
    assert_ne!(revision(&mut a), base);

    let err = a
        .call(
            "component.set",
            json!({
                "command_id": cid(),
                "id": id,
                "type": "Transform2D",
                "patch": { "x": 9.0, "y": 1.0 },
                "expected_revision": base,
            }),
        )
        .expect_err("stale writer must conflict");
    assert_eq!(err.code, CONFLICT);
    assert_eq!(app_code(&err), "E_CONFLICT");
}

#[test]
fn mutating_budget_200_per_minute() {
    let (dir, bus) = start_bus();
    let mut agent = bus.connect_agent("hungry").expect("hello");
    bus.ui()
        .call(
            "project.open",
            json!({ "path": dir.path().to_string_lossy().into_owned() }),
        )
        .expect("human_ui project.open does not consume the agent budget");

    let mut commands = Vec::with_capacity(200);
    for i in 0..200 {
        commands.push(json!({
            "method": "entity.spawn",
            "params": { "scene_id": "s_main", "name": format!("b{i}") },
        }));
    }
    agent
        .call(
            "transaction.execute",
            json!({
                "label": "fill-budget",
                "command_id": cid(),
                "commands": commands,
            }),
        )
        .expect("200 inner commands fill the per-minute budget exactly");
    assert_eq!(entity_count(&mut agent), 200);

    let err = agent
        .call(
            "entity.spawn",
            json!({
                "command_id": cid(),
                "scene_id": "s_main",
                "name": "over",
            }),
        )
        .expect_err("201st mutating command");
    assert_eq!(err.code, -32003);
    assert_eq!(app_code(&err), "E_BUDGET");
    assert_eq!(err.data.as_ref().and_then(|d| d.retryable), Some(true));
    assert_eq!(entity_count(&mut agent), 200);
}

#[test]
fn transaction_is_atomic_failing_command_applies_nothing() {
    let (dir, bus) = start_bus();
    let mut agent = bus.connect_agent("coder").expect("hello");
    open_project(&mut agent, dir.path());
    spawn_named(&mut agent, "keep", &cid());
    let before = revision(&mut agent);

    let err = agent
        .call(
            "transaction.execute",
            json!({
                "command_id": cid(),
                "label": "atomic-fail",
                "commands": [
                    {
                        "method": "entity.spawn",
                        "params": { "scene_id": "s_main", "name": "ghost" }
                    },
                    {
                        "method": "entity.rename",
                        "params": { "id": "e_000042", "name": "nope" }
                    }
                ],
            }),
        )
        .expect_err("failing inner command");
    assert_eq!(app_code(&err), "E_NOT_FOUND");
    assert_eq!(entity_count(&mut agent), 1);
    assert_eq!(revision(&mut agent), before);
}

#[test]
fn salami_destroy_elevates_to_destructive() {
    let (dir, bus) = start_bus();
    let mut agent = bus.connect_agent("slicer").expect("hello");
    open_project(&mut agent, dir.path());

    for wave in 0..3 {
        let mut ids = Vec::new();
        for i in 0..16 {
            let spawned = spawn_named(&mut agent, &format!("s{wave}_{i}"), &cid());
            ids.push(spawned["spawned_ids"][0].as_str().expect("id").to_owned());
        }
        let result = agent
            .call("entity.destroy", json!({ "command_id": cid(), "ids": ids }))
            .expect("first three 16-id destroys stay under D");
        assert_ne!(
            result.get("status").and_then(|v| v.as_str()),
            Some("pending_confirmation"),
            "wave {wave} must apply"
        );
    }
    assert_eq!(entity_count(&mut agent), 0);

    let mut ids = Vec::new();
    for i in 0..16 {
        let spawned = spawn_named(&mut agent, &format!("s3_{i}"), &cid());
        ids.push(spawned["spawned_ids"][0].as_str().expect("id").to_owned());
    }
    let held = agent
        .call("entity.destroy", json!({ "command_id": cid(), "ids": ids }))
        .expect("fourth 16-id destroy in 60s elevates to D");
    assert_eq!(held["status"], "pending_confirmation");
    assert_eq!(entity_count(&mut agent), 16);
    assert!(
        bus.ui()
            .heuristic_log()
            .iter()
            .any(|line| line.contains("salami")),
        "heuristic log must record the elevation"
    );
}

#[test]
fn path_jail_rejects_escape() {
    let (_dir, mut s) = open_session();
    let ack = spawn_session(&mut s, "root");
    let from = ack.spawned_ids[0].clone();
    let before = s.canonical_scene_bytes();
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::blueprint_create(from, "blueprints/../outside.gbp.json"),
        ))
        .unwrap_err();
    assert!(
        matches!(err, Error::PathEscapesRoot { .. }),
        "traversal must be PathEscapesRoot, got {err:?}"
    );
    assert_eq!(s.canonical_scene_bytes(), before);
}

#[test]
fn windows_reserved_name_rejected() {
    let (_dir, mut s) = open_session();
    let ack = spawn_session(&mut s, "root");
    let from = ack.spawned_ids[0].clone();
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::blueprint_create(from, "blueprints/CON.gbp.json"),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { reason, .. } => {
            assert!(
                reason.to_ascii_lowercase().contains("reserved") || reason.contains("CON"),
                "{reason}"
            );
        }
        other => panic!("expected Invalid reserved name, got {other:?}"),
    }
}
