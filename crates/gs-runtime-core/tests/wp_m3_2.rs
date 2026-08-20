use std::path::PathBuf;
use std::time::Duration;

use gs_runtime_core::{
    format_play_id, parse_play_id, InputFrame, ScriptHost, ScriptTimeHook, World, RUNTIME_ID_BASE,
    SPAWN_CAP_PER_FRAME,
};
use gs_scene::{
    AssetRef, Camera2D, Collider2D, ColliderShape, Entity, Name, Scene, Script, Sprite, Tags,
    Transform2D,
};
use serde_json::json;

const DOOR_7_5: &str = r#"--!strict
local M = {}

function M.on_init(self)
  -- self.props từ Script component (5.4): locked, key_tag, open_sprite
  if self.state.locked == nil then
    self.state.locked = self.props.locked
  end
end

function M.on_event(self, name, data)
  if name ~= "collision_enter" then return end
  if not self.state.locked then return end
  -- key_pickup.luau đã gs.add_tag(player, self.props.key_tag)
  if gs.has_tag(data.other, "player")
     and gs.has_tag(data.other, self.props.key_tag) then
    self.state.locked = false
    gs.set_sprite(self.id, self.props.open_sprite)
    gs.set_component(self.id, "Collider2D", { is_sensor = true })
    gs.emit("DoorOpened", { door = self.id, by = data.other })
  end
end

return M
"#;

fn templates_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../templates")
}

fn transform_at(x: f32, y: f32) -> Transform2D {
    Transform2D {
        x,
        y,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    }
}

fn camera() -> Entity {
    let mut entity = Entity::new(1, None, 0);
    entity.name = Some(Name {
        value: "MainCamera".into(),
    });
    entity.transform = Some(transform_at(0.0, 0.0));
    entity.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    entity
}

fn door_entity() -> Entity {
    let mut entity = Entity::new(42, None, 1);
    entity.name = Some(Name {
        value: "door_1".into(),
    });
    entity.tags = Some(Tags {
        values: vec!["door".into(), "interactive".into()],
    });
    entity.transform = Some(Transform2D {
        x: 4.5,
        y: 2.0,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 10,
    });
    entity.extra.sprite = Some(Sprite {
        asset: AssetRef {
            id: "a_000007".into(),
        },
        color: [1.0, 1.0, 1.0, 1.0],
        flip_x: false,
        flip_y: false,
        pivot: [0.5, 0.0],
    });
    entity.extra.collider = Some(Collider2D {
        shape: ColliderShape::Box { w: 1.0, h: 2.0 },
        is_sensor: false,
        offset: [0.0, 1.0],
        layer: 1,
        mask: u32::MAX,
        friction: 0.5,
        restitution: 0.0,
    });
    let mut props = std::collections::BTreeMap::new();
    props.insert("locked".into(), json!(true));
    props.insert("key_tag".into(), json!("key_gold"));
    props.insert("open_sprite".into(), json!({ "$asset": "a_000008" }));
    entity.extra.script = Some(Script {
        file: "scripts/door.luau".into(),
        props,
    });
    entity
}

fn player(tags: &[&str]) -> Entity {
    let mut entity = Entity::new(99, None, 2);
    entity.name = Some(Name {
        value: "player".into(),
    });
    entity.tags = Some(Tags {
        values: tags.iter().map(|t| (*t).to_string()).collect(),
    });
    entity.transform = Some(transform_at(4.5, 2.0));
    entity
}

fn door_world(player_tags: &[&str]) -> World {
    let mut scene = Scene::default();
    for entity in [camera(), door_entity(), player(player_tags)] {
        scene.entities.insert(entity.id, entity);
    }
    let mut world = World::from_scene(scene, 1);
    world
        .load_script_sources(&templates_root())
        .expect("load door.luau from templates/");
    world
}

fn body(id: u64) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(transform_at(0.0, 0.0));
    entity
}

fn simple_world(extra: Vec<Entity>) -> World {
    let mut scene = Scene::default();
    scene.entities.insert(1, camera());
    for entity in extra {
        scene.entities.insert(entity.id, entity);
    }
    World::from_scene(scene, 1)
}

#[test]
fn door_luau_matches_master_7_5() {
    let path = templates_root().join("scripts/door.luau");
    let text = std::fs::read_to_string(&path).expect("templates/scripts/door.luau");
    assert_eq!(text.replace("\r\n", "\n"), DOOR_7_5.replace("\r\n", "\n"));
}

#[test]
fn door_luau_unlocks_when_player_has_key() {
    let mut world = door_world(&["player", "key_gold"]);
    assert!(world.script_bindings.contains_key(&42));
    assert!(world
        .attached_scripts
        .get(&42)
        .is_some_and(|s| s.contains("return M")));

    let mut host = ScriptHost::new().expect("host");
    world.queue_collision_enter(42, 99, false);
    host.step(&mut world, &InputFrame::default()).expect("step");

    let state = host.state_json(42).expect("state");
    assert_eq!(state["locked"], json!(false));
    let door = world.entities.get(&42).expect("door lives");
    assert_eq!(
        door.extra.sprite.as_ref().map(|s| s.asset.id.as_str()),
        Some("a_000008")
    );
    assert_eq!(
        door.extra.collider.as_ref().map(|c| c.is_sensor),
        Some(true)
    );
    assert!(world.play_events.iter().any(|e| e.name == "DoorOpened"));
}

#[test]
fn door_luau_stays_locked_without_key() {
    let mut world = door_world(&["player"]);
    let mut host = ScriptHost::new().expect("host");
    world.queue_collision_enter(42, 99, false);
    host.step(&mut world, &InputFrame::default()).expect("step");

    let state = host.state_json(42).expect("state");
    assert_eq!(state["locked"], json!(true));
    let door = world.entities.get(&42).expect("door lives");
    assert_eq!(
        door.extra.sprite.as_ref().map(|s| s.asset.id.as_str()),
        Some("a_000007")
    );
    assert_eq!(
        door.extra.collider.as_ref().map(|c| c.is_sensor),
        Some(false)
    );
    assert!(!world.play_events.iter().any(|e| e.name == "DoorOpened"));
}

#[test]
fn self_state_persists_across_steps_on_same_host() {
    let mut world = simple_world(vec![body(2)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_init(self)
              if self.state.n == nil then
                self.state.n = 1
              end
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
    assert_eq!(state["n"], json!(1), "on_init must not reset n");
}

#[test]
fn three_hard_deadlines_disable_instance_reload_runs_again() {
    let mut world = simple_world(vec![body(2)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_update(self, dt)
              while true do end
            end
            return M
        "#,
    );
    world.script_time_hook = Some(ScriptTimeHook {
        advance_per_script: Duration::from_millis(4),
    });
    let mut host = ScriptHost::new().expect("host");
    for _ in 0..3 {
        host.step(&mut world, &InputFrame::default())
            .expect("deadline step");
    }
    assert!(host.is_disabled(2));
    assert!(world.entities.contains_key(&2));
    assert!(world
        .play_events
        .iter()
        .any(|e| e.name == "script_disabled"));

    host.step(&mut world, &InputFrame::default())
        .expect("disabled step");
    assert!(!world.scripts_ran.contains(&2));

    host.reload(&mut world, 2).expect("reload");
    assert!(!host.is_disabled(2));
    host.step(&mut world, &InputFrame::default())
        .expect("after reload");
    assert!(world.scripts_ran.contains(&2));
}

#[test]
fn ten_runtime_errors_in_ten_seconds_disable() {
    let mut world = simple_world(vec![body(2)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_update(self, dt)
              error("boom")
            end
            return M
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    for i in 0..10 {
        world.script_now_ms = Some(i * 100);
        host.step(&mut world, &InputFrame::default())
            .expect("error step");
    }
    assert!(host.is_disabled(2));
    assert!(world
        .play_events
        .iter()
        .any(|e| e.name == "script_disabled"));
    let last = world.script_errors.last().expect("diag");
    assert!(last.line.is_some() || last.file.is_some());
}

#[test]
fn gs_ec_25_dead_id_is_nil_false_no_error() {
    let mut world = simple_world(vec![body(2), body(3)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_update(self, dt)
              local held = "e_000003"
              if gs.exists(held) then
                gs.destroy(held)
              end
              if gs.exists(held) then
                error("exists must be false")
              end
              local x, y = gs.get_pos(held)
              if x ~= nil or y ~= nil then
                error("get_pos must be nil")
              end
              if gs.get_component(held, "Transform2D") ~= nil then
                error("get_component must be nil")
              end
              if gs.has_tag(held, "player") then
                error("has_tag must be false")
              end
            end
            return M
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default()).expect("step");
    assert!(!world.entities.contains_key(&3));
    assert!(world
        .script_errors
        .iter()
        .all(|e| e.entity_id != 2 || e.deadline));
    assert!(world.script_errors.iter().all(|e| e.entity_id != 2));
}

#[test]
fn spawn_allocates_rt_ids_and_rejects_over_cap() {
    let mut world = simple_world(vec![body(2)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_init(self)
              self.state.a = gs.spawn("unused.gbp.json", {x=1, y=2})
              self.state.b = gs.spawn("unused.gbp.json", {x=3, y=4})
              local last = nil
              for i = 3, 1001 do
                last = gs.spawn("unused.gbp.json", {x=0, y=0})
              end
              self.state.last = last
              self.state.alive = gs.exists("rt_1")
            end
            return M
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default()).expect("step");
    let state = host.state_json(2).expect("state");
    assert_eq!(state["a"], json!("rt_1"));
    assert_eq!(state["b"], json!("rt_2"));
    assert_eq!(state["last"], json!(null));
    assert_eq!(state["alive"], json!(true));
    assert_eq!(parse_play_id("rt_1"), Some(RUNTIME_ID_BASE + 1));
    assert_eq!(format_play_id(RUNTIME_ID_BASE + 1), "rt_1");
    assert!(world.entities.contains_key(&(RUNTIME_ID_BASE + 1)));
    assert!(world.entities.contains_key(&(RUNTIME_ID_BASE + 2)));
    assert!(!world.entities.contains_key(&(RUNTIME_ID_BASE + 1001)));
    assert_eq!(world.entities.get(&1).map(|e| e.id), Some(1));
    assert_eq!(
        world
            .entities
            .values()
            .filter(|e| e.id >= RUNTIME_ID_BASE)
            .count(),
        SPAWN_CAP_PER_FRAME as usize
    );
    assert!(world
        .warnings
        .iter()
        .any(|w| w.contains("gs.spawn rejected")));
}
