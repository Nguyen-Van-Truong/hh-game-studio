//! GS-EC-05 automated gap: scene_max 50k / warn 20k are not in gs-scene.
//! GS-EC-12 lives in `gs-editor` `wp_m1_3` (mapped in docs/M1-GS-EC.md).
//! GS-EC-46 / 47 are manual (same doc).

use std::collections::BTreeMap;

use gs_scene::{Command, DispatchRequest, Document, Error, Session, DEFAULT_SCENE_ID};
use m1::GS_EC_05_WARN_COUNT;
use tempfile::TempDir;
use ulid::Ulid;

fn cid() -> String {
    Ulid::new().to_string()
}

fn spawn_batch(n: usize, start: usize) -> Vec<Command> {
    (0..n)
        .map(|i| {
            Command::entity_spawn(
                DEFAULT_SCENE_ID,
                Some(format!("e{}", start + i)),
                None,
                BTreeMap::new(),
            )
        })
        .collect()
}

#[test]
fn gs_ec_05_document_accepts_count_above_warn_threshold() {
    // Honest: no scene_max / 20k warning in gs-scene (see docs/M1-GS-EC.md).
    let mut doc = Document::default();
    const BATCH: usize = 200;
    assert_eq!(
        GS_EC_05_WARN_COUNT % BATCH,
        0,
        "warn count must be a whole number of max-sized txns"
    );
    let batches = GS_EC_05_WARN_COUNT / BATCH;
    for b in 0..batches {
        doc.apply_txn(&spawn_batch(BATCH, b * BATCH))
            .expect("GS-EC-05 cap is not implemented; apply must succeed");
    }
    assert_eq!(doc.entity_count(), GS_EC_05_WARN_COUNT);
}

#[test]
fn gs_ec_05_session_max_txn_spawn_is_uncapped_by_scene_max() {
    let dir = TempDir::new().expect("tempdir");
    let mut session = Session::open(dir.path()).expect("session");
    let ack = session
        .dispatch(DispatchRequest::transaction(
            cid(),
            "act_01",
            spawn_batch(200, 0),
        ))
        .expect("200-spawn txn (MAX_TXN_COMMANDS) must not hit a scene cap");
    assert_eq!(ack.spawned_ids.len(), 200);
    assert_eq!(session.document().entity_count(), 200);
}

#[test]
fn gs_ec_05_error_enum_has_no_scene_cap_variant() {
    let samples = [
        Error::NotFound("e_1".into()).to_string(),
        Error::invalid("entity.spawn", "test").to_string(),
        Error::UnknownMethod("nope".into()).to_string(),
    ];
    for s in samples {
        let lower = s.to_ascii_lowercase();
        assert!(
            !lower.contains("scene_max") && !lower.contains("50k"),
            "unexpected cap wording: {s}"
        );
    }
}
