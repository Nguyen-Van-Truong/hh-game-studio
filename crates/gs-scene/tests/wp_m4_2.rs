//! WP-M4-2 document half: tilemap.set_cells / tilemap.fill_rect + GS-EC-06.

use std::collections::BTreeMap;

use gs_scene::{Command, DispatchRequest, Error, Session, DEFAULT_SCENE_ID};
use serde_json::{json, Value};
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

fn dispatch(session: &mut Session, command: Command) -> gs_scene::Ack {
    session
        .dispatch(DispatchRequest::new(cid(), "act_01", command))
        .expect("dispatch")
}

fn spawn_tilemap(session: &mut Session, cells: Value) -> String {
    let mut comps = BTreeMap::new();
    comps.insert(
        "Tilemap".into(),
        json!({
            "tileset": { "$asset": "a_000001" },
            "cell_size": [1.0, 1.0],
            "layers": [{ "name": "ground", "solid": true, "cells": cells }]
        }),
    );
    dispatch(
        session,
        Command::entity_spawn(DEFAULT_SCENE_ID, Some("map".into()), None, comps),
    )
    .spawned_ids[0]
        .clone()
}

fn layer_cells(session: &Session, id: &str) -> Vec<[i64; 4]> {
    let n = gs_scene::parse_entity_id(id).expect("id");
    session
        .document()
        .entity(n)
        .and_then(|e| e.extra.tilemap.as_ref())
        .and_then(|t| t.layers.first())
        .map(|l| l.cells.clone())
        .expect("tilemap layer")
}

#[test]
fn set_cells_then_get_cells_undo_restores() {
    let (_dir, mut s) = open_tmp();
    let id = spawn_tilemap(&mut s, json!([[0, 0, 3, 1]]));
    assert_eq!(layer_cells(&s, &id), vec![[0, 0, 3, 1]]);

    dispatch(
        &mut s,
        Command::tilemap_set_cells(
            id.clone(),
            json!("ground"),
            json!([[1, 0, 2, 2], [4, 1, 7]]),
        ),
    );
    assert_eq!(
        layer_cells(&s, &id),
        vec![[0, 0, 1, 1], [1, 0, 2, 2], [4, 1, 1, 7]]
    );

    s.undo_last(&cid(), "act_01").expect("undo set_cells");
    assert_eq!(layer_cells(&s, &id), vec![[0, 0, 3, 1]]);
}

#[test]
fn fill_rect_writes_row_rle_merged() {
    let (_dir, mut s) = open_tmp();
    let id = spawn_tilemap(&mut s, json!([[0, 0, 3, 1]]));
    dispatch(
        &mut s,
        Command::tilemap_fill_rect(id.clone(), json!(0), 3, 0, 2, 1, 1),
    );
    assert_eq!(layer_cells(&s, &id), vec![[0, 0, 5, 1]]);
}

#[test]
fn million_expanded_cells_rejected() {
    let (_dir, mut s) = open_tmp();
    let id = spawn_tilemap(&mut s, json!([[0, 0, 3, 1]]));

    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::tilemap_set_cells(id.clone(), json!("ground"), json!([[0, 0, 1_000_001, 1]])),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { method, reason } => {
            assert_eq!(method, "tilemap.set_cells");
            assert!(
                reason.contains("1_000_000") || reason.contains("1000000"),
                "reason={reason}"
            );
            assert!(reason.contains("split"), "reason={reason}");
        }
        other => panic!("expected Invalid, got {other:?}"),
    }

    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::tilemap_fill_rect(id.clone(), json!("ground"), 0, 0, 1_000_001, 1, 1),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { method, reason } => {
            assert_eq!(method, "tilemap.fill_rect");
            assert!(
                reason.contains("1_000_000") || reason.contains("1000000"),
                "reason={reason}"
            );
            assert!(reason.contains("split"), "reason={reason}");
        }
        other => panic!("expected Invalid, got {other:?}"),
    }

    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::component_set(
                id,
                "Tilemap",
                json!({
                    "layers": [{
                        "name": "ground",
                        "solid": true,
                        "cells": [[0, 0, 1_000_001, 1]]
                    }]
                }),
            ),
        ))
        .unwrap_err();
    match err {
        Error::Invalid { reason, .. } => {
            assert!(
                reason.contains("1_000_000") || reason.contains("1000000"),
                "reason={reason}"
            );
            assert!(reason.contains("split"), "reason={reason}");
        }
        other => panic!("expected Invalid from parse, got {other:?}"),
    }

    assert_eq!(s.document().entity_count(), 1);
}

#[test]
fn missing_entity_is_not_found() {
    let (_dir, mut s) = open_tmp();
    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::tilemap_set_cells("e_000099", json!("ground"), json!([[0, 0, 1, 1]])),
        ))
        .unwrap_err();
    assert!(
        matches!(err, Error::NotFound(ref id) if id == "e_000099"),
        "got {err:?}"
    );

    let err = s
        .dispatch(DispatchRequest::new(
            cid(),
            "act_01",
            Command::new(
                "tilemap.fill_rect",
                json!({
                    "entity_id": "e_000099",
                    "layer": "ground",
                    "x": 0,
                    "y": 0,
                    "w": 1,
                    "h": 1,
                    "tile": 1
                }),
            ),
        ))
        .unwrap_err();
    assert!(
        matches!(err, Error::NotFound(ref id) if id == "e_000099"),
        "got {err:?}"
    );
}
