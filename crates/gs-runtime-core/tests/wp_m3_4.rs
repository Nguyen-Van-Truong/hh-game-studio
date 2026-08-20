use gs_runtime_core::{InputFrame, ScriptHost, World};
use gs_scene::{Camera2D, Entity, Scene, Transform2D};

fn camera() -> Entity {
    let mut entity = Entity::new(1, None, 0);
    entity.transform = Some(Transform2D::identity());
    entity.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    entity
}

fn body(id: u64) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(Transform2D::identity());
    entity
}

fn world_with_script(source: &str) -> World {
    let mut scene = Scene::default();
    scene.entities.insert(1, camera());
    scene.entities.insert(2, body(2));
    let mut world = World::from_scene(scene, 1);
    world.attach_script(2, source);
    world
}

fn json_f64(value: &serde_json::Value) -> f64 {
    value.as_f64().expect("numeric state")
}

#[test]
fn gs_action_reads_move_x_axis_from_input_frame() {
    let mut world = world_with_script(
        r#"
            local M = {}
            function M.on_update(self, dt)
              self.state.move_x = gs.action("move_x")
            end
            return M
        "#,
    );
    let mut input = InputFrame::default();
    input.actions.insert("move_x".into(), 1.0);
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &input).expect("step");

    let state = host.state_json(2).expect("state");
    assert_eq!(json_f64(&state["move_x"]), 1.0);
    assert!(world.script_errors.is_empty());
}

#[test]
fn gs_action_missing_name_returns_zero_and_warns_once() {
    let mut world = world_with_script(
        r#"
            local M = {}
            function M.on_update(self, dt)
              self.state.a = gs.action("not_bound")
              self.state.b = gs.action("not_bound")
            end
            return M
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default())
        .expect("step 1");
    host.step(&mut world, &InputFrame::default())
        .expect("step 2");

    let state = host.state_json(2).expect("state");
    assert_eq!(json_f64(&state["a"]), 0.0);
    assert_eq!(json_f64(&state["b"]), 0.0);
    let warnings: Vec<_> = world
        .warnings
        .iter()
        .filter(|w| w.contains("not_bound"))
        .collect();
    assert_eq!(
        warnings.len(),
        1,
        "one warning per missing name, got {warnings:?}"
    );
    assert!(world.script_errors.is_empty());
}

#[test]
fn gs_action_reads_interact_button() {
    let mut world = world_with_script(
        r#"
            local M = {}
            function M.on_update(self, dt)
              self.state.interact = gs.action("interact")
            end
            return M
        "#,
    );
    let mut input = InputFrame::default();
    input.actions.insert("interact".into(), 1.0);
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &input).expect("step");

    let state = host.state_json(2).expect("state");
    assert_eq!(json_f64(&state["interact"]), 1.0);
    assert!(world.script_errors.is_empty());
}
