//! M0 entity.lock / project.settings_* via Session::dispatch (I1/I2/I11).

use std::collections::BTreeMap;
use std::time::{Duration, Instant};

use gs_scene::{Command, DispatchRequest, Error, Session, Transform2D, DEFAULT_SCENE_ID, LOCK_TTL};
use serde_json::json;
use tempfile::TempDir;
use ulid::Ulid;

fn open_tmp() -> (TempDir, Session) {
    let dir = TempDir::new().expect("tempdir");
    let session = Session::open(dir.path()).expect("open");
    (dir, session)
}

fn cid() -> String {
    Ulid::new().to_string()
}

fn spawn(session: &mut Session, actor: &str, name: &str) -> String {
    session
        .dispatch(DispatchRequest::spawn(cid(), actor, DEFAULT_SCENE_ID, name))
        .expect("spawn")
        .spawned_ids[0]
        .clone()
}

fn lock(
    session: &mut Session,
    actor: &str,
    ids: Vec<String>,
    note: &str,
) -> Result<gs_scene::Ack, Error> {
    session.dispatch(DispatchRequest::new(
        cid(),
        actor,
        Command::entity_lock(ids, Some(note.to_string())),
    ))
}

fn unlock(
    session: &mut Session,
    actor: &str,
    ids: Vec<String>,
    force: bool,
) -> Result<gs_scene::Ack, Error> {
    session.dispatch(DispatchRequest::new(
        cid(),
        actor,
        Command::entity_unlock(ids, force),
    ))
}

fn set_x(session: &mut Session, actor: &str, id: &str, x: f32) -> Result<gs_scene::Ack, Error> {
    let mut t = Transform2D::identity();
    t.x = x;
    session.dispatch(DispatchRequest::set_transform(cid(), actor, id, t))
}

#[test]
fn lock_then_other_actor_component_set_is_locked() {
    let (_dir, mut s) = open_tmp();
    let id = spawn(&mut s, "act_a", "hero");
    let ack = lock(&mut s, "act_a", vec![id.clone()], "editing sprite").expect("lock");
    assert!(ack.owner_token.as_ref().is_some_and(|t| !t.is_empty()));

    let err = set_x(&mut s, "act_b", &id, 9.0).unwrap_err();
    match err {
        Error::Locked { owner, note, .. } => {
            assert_eq!(owner, "act_a");
            assert_eq!(note, "editing sprite");
        }
        other => panic!("expected Locked, got {other:?}"),
    }
}

#[test]
fn same_actor_can_mutate_locked_entity() {
    let (_dir, mut s) = open_tmp();
    let id = spawn(&mut s, "act_a", "hero");
    lock(&mut s, "act_a", vec![id.clone()], "mine").expect("lock");
    set_x(&mut s, "act_a", &id, 3.0).expect("owner set");
    let ent = s.document().entity(1).expect("entity");
    assert_eq!(ent.transform.as_ref().map(|t| t.x), Some(3.0));
}

#[test]
fn unlock_releases_entity() {
    let (_dir, mut s) = open_tmp();
    let id = spawn(&mut s, "act_a", "hero");
    lock(&mut s, "act_a", vec![id.clone()], "hold").expect("lock");
    unlock(&mut s, "act_a", vec![id.clone()], false).expect("unlock");
    set_x(&mut s, "act_b", &id, 4.0).expect("other set after unlock");
}

#[test]
fn expire_after_60s_releases_lock() {
    let (_dir, mut s) = open_tmp();
    let id = spawn(&mut s, "act_a", "hero");
    let t0 = Instant::now();
    s.set_clock(t0);
    lock(&mut s, "act_a", vec![id.clone()], "ttl").expect("lock");
    s.set_clock(t0 + LOCK_TTL + Duration::from_millis(1));
    set_x(&mut s, "act_b", &id, 5.0).expect("set after expire");
}

#[test]
fn quota_101st_lock_fails() {
    let (_dir, mut s) = open_tmp();
    let mut cmds = Vec::new();
    for i in 0..101 {
        cmds.push(Command::entity_spawn(
            DEFAULT_SCENE_ID,
            Some(format!("e{i}")),
            None,
            BTreeMap::new(),
        ));
    }
    s.dispatch(DispatchRequest::transaction(cid(), "act_a", cmds))
        .expect("spawn 101");
    let mut ids: Vec<String> = s
        .document()
        .scene
        .entities
        .keys()
        .copied()
        .map(gs_scene::format_entity_id)
        .collect();
    ids.sort();
    assert_eq!(ids.len(), 101);

    lock(&mut s, "act_a", ids[..100].to_vec(), "batch").expect("100 locks");
    assert_eq!(s.lock_count_for("act_a"), 100);
    let err = lock(&mut s, "act_a", vec![ids[100].clone()], "one more").unwrap_err();
    match err {
        Error::Invalid { method, reason } => {
            assert_eq!(method, "entity.lock");
            assert!(reason.contains("quota"), "reason={reason}");
        }
        other => panic!("expected quota Invalid, got {other:?}"),
    }
}

#[test]
fn agent_cannot_force_unlock_other_actor() {
    let (_dir, mut s) = open_tmp();
    let id = spawn(&mut s, "act_a", "hero");
    lock(&mut s, "act_a", vec![id.clone()], "keep").expect("lock");
    let err = unlock(&mut s, "act_b", vec![id.clone()], false).unwrap_err();
    assert!(matches!(err, Error::Locked { owner, .. } if owner == "act_a"));
}

#[test]
fn human_force_unlock_releases() {
    let (_dir, mut s) = open_tmp();
    let id = spawn(&mut s, "act_a", "hero");
    lock(&mut s, "act_a", vec![id.clone()], "keep").expect("lock");
    unlock(&mut s, "act_ui", vec![id.clone()], true).expect("force unlock");
    set_x(&mut s, "act_b", &id, 1.0).expect("set after force");
}

#[test]
fn disconnect_releases_actor_locks() {
    let (_dir, mut s) = open_tmp();
    let id = spawn(&mut s, "act_a", "hero");
    lock(&mut s, "act_a", vec![id.clone()], "session").expect("lock");
    s.release_locks_for_actor("act_a");
    set_x(&mut s, "act_b", &id, 2.0).expect("set after disconnect");
}

#[test]
fn lock_renew_returns_same_token() {
    let (_dir, mut s) = open_tmp();
    let id = spawn(&mut s, "act_a", "hero");
    let first = lock(&mut s, "act_a", vec![id.clone()], "v1").expect("lock");
    let second = lock(&mut s, "act_a", vec![id.clone()], "v2").expect("renew");
    assert_eq!(first.owner_token, second.owner_token);
}

#[test]
fn settings_set_round_trip_keeps_unknown_field() {
    let (dir, mut s) = open_tmp();
    s.dispatch(DispatchRequest::new(
        cid(),
        "act_a",
        Command::project_settings_set(json!({
            "fixed_dt": 0.02,
            "ppu": 32,
            "x-custom": "keep-me",
        })),
    ))
    .expect("settings_set");

    let got = s.read_project_settings();
    assert_eq!(got["ppu"], json!(32));
    assert!((got["fixed_dt"].as_f64().unwrap() - 0.02).abs() < 1e-9);
    assert_eq!(got["x-custom"], json!("keep-me"));

    let on_disk: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(dir.path().join("project.json")).expect("project.json"),
    )
    .expect("json");
    assert_eq!(on_disk["x-custom"], json!("keep-me"));
    assert_eq!(on_disk["ppu"], json!(32));

    drop(s);
    let s2 = Session::open(dir.path()).expect("reopen");
    let again = s2.read_project_settings();
    assert_eq!(again["x-custom"], json!("keep-me"));
    assert_eq!(again["ppu"], json!(32));
    assert!((again["fixed_dt"].as_f64().unwrap() - 0.02).abs() < 1e-9);
}
