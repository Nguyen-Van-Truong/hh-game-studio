//! WP-M1-2: pick (G1) + view-state pan/zoom must not write WAL (I1).
//! No eframe window is opened.

use gs_editor::{apply_view_navigation, world_to_pixel, ViewState};
use gs_render2d::{pick, RenderItem, RenderSnapshot};
use gs_scene::Session;
use tempfile::TempDir;

#[test]
fn pick_physical_pixel_returns_expected_entity_id() {
    let item = RenderItem::new(42, 0, 0.0, 0.0, 2.0, 2.0, [1.0, 0.2, 0.2, 1.0], None);
    let snapshot = RenderSnapshot {
        camera: gs_render2d::Camera2D {
            ortho_height: 10.0,
            position: [0.0, 0.0],
        },
        items: vec![item],
    };
    let atlas = gs_render2d::demo_atlas();
    let (vw, vh) = (640.0, 360.0);
    let [px, py] = world_to_pixel(1.0, 1.0, vw, vh, &snapshot.camera);
    assert_eq!(pick(&snapshot, &atlas, px, py, vw, vh), Some(42));

    let [miss_x, miss_y] = world_to_pixel(-4.0, 4.0, vw, vh, &snapshot.camera);
    assert_eq!(pick(&snapshot, &atlas, miss_x, miss_y, vw, vh), None);
}

#[test]
fn view_state_pan_zoom_does_not_increment_revision() {
    let dir = TempDir::new().expect("tempdir");
    let session = Session::open(dir.path()).expect("open session");
    let before_rev = session.document().revision;
    let before_label = session.document().revision_label();
    let before_seq = session.last_ack().seq;

    let mut view = ViewState::default();
    apply_view_navigation(&mut view, [3.0, -2.0], 0.5);
    view.set_grid(false);
    view.set_snap(true);
    let _ = view.snap_point([1.4, 2.6]);

    assert_eq!(view.position, [3.0, -2.0]);
    assert!((view.ortho_height - 5.0).abs() < f32::EPSILON);
    assert_eq!(session.document().revision, before_rev);
    assert_eq!(session.document().revision_label(), before_label);
    assert_eq!(
        session.last_ack().seq,
        before_seq,
        "pan/zoom must not append a WAL/ACK record"
    );
}
