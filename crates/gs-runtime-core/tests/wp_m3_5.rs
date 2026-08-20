//! MASTER 7.6 Luau test matrix + GS-EC-22..26, 34, 37 (WP-M3-5).
//!
//! Long-lived [`ScriptHost`] only. Fake time is used except the existing
//! real while-true in `script::tests` (M3-1).

use std::time::Duration;

use gs_runtime_core::{
    parse_play_id, InputFrame, ScriptError, ScriptHost, ScriptTimeHook, World, INIT_BUDGET,
    RUNTIME_ID_BASE, SCRIPT_HARD, SPAWN_CAP_PER_FRAME,
};
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

fn body_at(id: u64, x: f32, y: f32) -> Entity {
    let mut entity = Entity::new(id, None, 1);
    entity.transform = Some(Transform2D {
        x,
        y,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    });
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

fn pos(world: &World, id: u64) -> (f32, f32) {
    let t = world
        .entities
        .get(&id)
        .and_then(|e| e.transform.as_ref())
        .expect("transform");
    (t.x, t.y)
}

fn fake_script_ms(ms: u64) -> ScriptTimeHook {
    ScriptTimeHook {
        advance_per_script: Duration::from_millis(ms),
    }
}

fn has_deadline(world: &World, id: u64) -> bool {
    world
        .script_errors
        .iter()
        .any(|e| e.entity_id == id && e.deadline)
}

fn module_loop(callback: &str) -> String {
    format!(
        r#"
            local M = {{}}
            function M.{callback}(self, dt)
              local i = 0
              while true do
                i += 1
              end
              gs.set_pos(self.id, 1, 1)
            end
            return M
        "#
    )
}

/// 7.6.1 / GS-EC-22 — infinite `on_update` hits deadline; buffer discarded.
#[test]
fn on_update_infinite_loop_hits_deadline() {
    let mut world = simple_world(vec![body(2)]);
    world.attach_script(2, module_loop("on_update"));
    world.script_time_hook = Some(fake_script_ms(SCRIPT_HARD.as_millis() as u64));
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default())
        .expect("player lives");

    assert!(has_deadline(&world, 2), "{:?}", world.script_errors);
    assert_eq!(pos(&world, 2), (0.0, 0.0));
    let report = host.vm().last_report().expect("report");
    assert!(report.cancelled);
    assert!(report.interrupts > 0);
    assert!(world.entities.contains_key(&2));
}

/// 7.6.2 / GS-EC-22 — infinite `on_init` uses the 100ms init budget.
#[test]
fn on_init_infinite_loop_hits_deadline() {
    assert_eq!(INIT_BUDGET, Duration::from_millis(100));
    let mut world = simple_world(vec![body(2)]);
    world.attach_script(2, module_loop("on_init"));
    world.script_time_hook = Some(fake_script_ms(INIT_BUDGET.as_millis() as u64));
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default())
        .expect("player lives");

    assert!(has_deadline(&world, 2), "{:?}", world.script_errors);
    assert_eq!(pos(&world, 2), (0.0, 0.0));
    let report = host.vm().last_report().expect("report");
    assert!(report.cancelled);
    assert!(report.interrupts > 0);
}

/// 7.6.3 / GS-EC-24 — `pcall` cannot lift the host cancel flag.
#[test]
fn pcall_cannot_swallow_deadline() {
    let mut world = simple_world(vec![body(2)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_update(self, dt)
              pcall(function()
                while true do end
              end)
              gs.set_pos(self.id, 1, 1)
            end
            return M
        "#,
    );
    world.script_time_hook = Some(fake_script_ms(SCRIPT_HARD.as_millis() as u64));
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default())
        .expect("player lives");

    assert!(has_deadline(&world, 2), "{:?}", world.script_errors);
    assert_eq!(pos(&world, 2), (0.0, 0.0));
    assert!(host.vm().last_report().is_some_and(|r| r.cancelled));
}

/// 7.6.4 — long-running `__index` / `__add` still hit interrupt.
#[test]
fn metamethod_loop_hits_interrupt() {
    let mut world = simple_world(vec![body(2), body(3)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_update(self, dt)
              local t = setmetatable({}, {
                __index = function(_, _)
                  local i = 0
                  while true do
                    i += 1
                  end
                end,
              })
              local _ = t.loop
              gs.set_pos(self.id, 1, 1)
            end
            return M
        "#,
    );
    world.attach_script(
        3,
        r#"
            local M = {}
            function M.on_update(self, dt)
              local a = setmetatable({}, {
                __add = function(_, _)
                  local i = 0
                  while true do
                    i += 1
                  end
                end,
              })
              local _ = a + a
              gs.set_pos(self.id, 1, 1)
            end
            return M
        "#,
    );
    world.script_time_hook = Some(fake_script_ms(SCRIPT_HARD.as_millis() as u64));
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default())
        .expect("player lives");

    assert!(
        has_deadline(&world, 2),
        " __index {:?}",
        world.script_errors
    );
    assert!(has_deadline(&world, 3), " __add {:?}", world.script_errors);
    assert_eq!(pos(&world, 2), (0.0, 0.0));
    assert_eq!(pos(&world, 3), (0.0, 0.0));
}

/// 7.6.5 — a script-created looping coroutine cannot escape the deadline.
#[test]
fn coroutine_loop_cannot_escape_deadline() {
    let mut world = simple_world(vec![body(2)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_update(self, dt)
              local co = coroutine.create(function()
                local i = 0
                while true do
                  i += 1
                end
              end)
              coroutine.resume(co)
              gs.set_pos(self.id, 1, 1)
            end
            return M
        "#,
    );
    world.script_time_hook = Some(fake_script_ms(SCRIPT_HARD.as_millis() as u64));
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default())
        .expect("process lives");

    assert!(has_deadline(&world, 2), "{:?}", world.script_errors);
    assert_eq!(pos(&world, 2), (0.0, 0.0));
    assert!(world.entities.contains_key(&1));
    assert!(world.entities.contains_key(&2));

    host.step(&mut world, &InputFrame::default())
        .expect("host still steps");
    assert!(world.entities.contains_key(&2));
}

/// 7.6.6 / GS-EC-23 — huge table/string alloc → MemoryError; host lives.
#[test]
fn memory_bomb_returns_memory_error_host_lives() {
    const TEST_LIMIT: usize = 2 * 1024 * 1024;
    let mut world = simple_world(vec![body(2)]);
    let host = ScriptHost::with_memory_limit(TEST_LIMIT).expect("host");
    let err = host
        .vm()
        .exec(
            &mut world,
            r#"
                local t = {}
                local i = 0
                while true do
                  i += 1
                  t[i] = string.rep("x", 4096)
                end
            "#,
            Duration::from_secs(5),
        )
        .expect_err("memory bomb must fail");
    assert!(
        matches!(err, ScriptError::Memory),
        "GS-EC-23 expected Memory, got {err}"
    );
    assert!(host.vm().used_memory() > 0);
    let again = host.vm().exec(
        &mut world,
        "gs.log(\"info\", \"alive\")",
        Duration::from_secs(1),
    );
    assert!(
        again.is_ok() || matches!(again, Err(ScriptError::Memory)),
        "host/VM must still exist: {again:?}"
    );
}

/// 7.6.7 — `gs.*` in `on_destroy` commits when the callback returns OK.
#[test]
fn gs_in_on_destroy_commits_when_ok() {
    let mut world = simple_world(vec![body(2), body(3)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_destroy(self)
              gs.set_pos(self.id, 7, 8)
              gs.log("info", "destroy_ok")
            end
            return M
        "#,
    );
    world.attach_script(
        3,
        r#"
            local M = {}
            function M.on_update(self, dt)
              gs.set_pos(self.id, 2, 2)
            end
            return M
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default()).expect("init");
    assert_eq!(pos(&world, 2), (0.0, 0.0));

    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_init(self)
              self.state.gen = 2
            end
            return M
        "#,
    );
    host.reload(&mut world, 2).expect("reload");
    assert_eq!(pos(&world, 2), (7.0, 8.0));
    assert_eq!(
        host.state_json(2).expect("state")["gen"],
        serde_json::json!(2)
    );
    assert!(world
        .script_logs
        .iter()
        .any(|l| l.message.contains("destroy_ok")));

    world.attach_script(
        3,
        r#"
            local M = {}
            function M.on_update(self, dt)
              if gs.exists("e_000002") then
                gs.destroy("e_000002")
              end
            end
            return M
        "#,
    );
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_destroy(self)
              gs.set_pos("e_000003", 5, 6)
              gs.log("info", "peer_destroy")
            end
            return M
        "#,
    );
    host.reload(&mut world, 2).expect("reload victim");
    host.reload(&mut world, 3).expect("reload destroyer");
    host.step(&mut world, &InputFrame::default())
        .expect("peer destroy");
    assert!(!world.entities.contains_key(&2));
    assert_eq!(pos(&world, 3), (5.0, 6.0));
}

/// 7.6.7 — `gs.*` in `on_destroy` discards on error and must not panic.
#[test]
fn gs_in_on_destroy_discards_on_error() {
    let mut world = simple_world(vec![body_at(2, 3.0, 4.0)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_destroy(self)
              gs.set_pos(self.id, 7, 8)
              gs.log("info", "destroy_fail")
              error("destroy boom")
            end
            return M
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default()).expect("init");

    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_init(self)
              self.state.survived = true
            end
            return M
        "#,
    );
    host.reload(&mut world, 2).expect("reload must not panic");
    assert_eq!(pos(&world, 2), (3.0, 4.0));
    assert_eq!(
        host.state_json(2).expect("state")["survived"],
        serde_json::json!(true)
    );
    host.step(&mut world, &InputFrame::default())
        .expect("host still steps");
    assert!(world.entities.contains_key(&2));
}

/// 7.6.8 / GS-EC-37 — recursive `gs.spawn` of the same blueprint hits cap 1000.
#[test]
fn recursive_spawn_hits_frame_cap() {
    let mut world = simple_world(vec![body(2)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_init(self)
              local function boom()
                local id = gs.spawn("self.gbp.json", {x = 0, y = 0})
                if id == nil then
                  self.state.rejected = true
                  return
                end
                self.state.last = id
                boom()
              end
              boom()
              self.state.alive = gs.exists("rt_1")
            end
            return M
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default()).expect("step");

    let state = host.state_json(2).expect("state");
    assert_eq!(state["rejected"], serde_json::json!(true));
    assert_eq!(state["last"], serde_json::json!("rt_1000"));
    assert_eq!(state["alive"], serde_json::json!(true));
    assert_eq!(parse_play_id("rt_1"), Some(RUNTIME_ID_BASE + 1));
    assert!(!world.entities.contains_key(&(RUNTIME_ID_BASE + 1001)));
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

/// 7.6.9 / GS-EC-34 lite — reload between frames; next `step` runs new source.
#[test]
fn reload_while_paused_applies_on_next_step() {
    let mut world = simple_world(vec![body(2)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_init(self)
              self.state.gen = 1
            end
            function M.on_update(self, dt)
              gs.set_pos(self.id, 1, 1)
            end
            return M
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default()).expect("old");
    assert_eq!(
        host.state_json(2).expect("state")["gen"],
        serde_json::json!(1)
    );
    assert_eq!(pos(&world, 2), (1.0, 1.0));

    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_init(self)
              self.state.gen = 2
            end
            function M.on_update(self, dt)
              gs.set_pos(self.id, 9, 9)
            end
            return M
        "#,
    );
    host.step(&mut world, &InputFrame::default())
        .expect("no reload yet");
    assert_eq!(
        host.state_json(2).expect("state")["gen"],
        serde_json::json!(1),
        "source must not swap mid-session without reload"
    );
    assert_eq!(pos(&world, 2), (1.0, 1.0));

    host.reload(&mut world, 2).expect("reload between frames");
    assert_eq!(
        host.state_json(2).expect("state")["gen"],
        serde_json::json!(2),
        "on_init of the new module runs at reload (between frames)"
    );
    assert_eq!(pos(&world, 2), (1.0, 1.0));

    host.step(&mut world, &InputFrame::default())
        .expect("step after reload");
    assert_eq!(pos(&world, 2), (9.0, 9.0));
}

/// 7.6.10 — two scripts write one component; later run (id order) wins.
#[test]
fn two_scripts_same_component_later_run_wins() {
    let mut world = simple_world(vec![body(2), body(3), body(4)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_update(self, dt)
              gs.set_component("e_000004", "Transform2D", {x = 1, y = 1})
              gs.set_pos("e_000004", 1, 1)
            end
            return M
        "#,
    );
    world.attach_script(
        3,
        r#"
            local M = {}
            function M.on_update(self, dt)
              gs.set_component("e_000004", "Transform2D", {x = 9, y = 9})
              gs.set_pos("e_000004", 9, 9)
            end
            return M
        "#,
    );
    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default()).expect("step");

    assert_eq!(world.scripts_ran, vec![2, 3]);
    assert_eq!(
        pos(&world, 4),
        (9.0, 9.0),
        "commit order follows run order (id ascending)"
    );
}

/// 7.6.11 / GS-EC-26 — starved scripts run first next frame.
#[test]
fn starved_scripts_run_first_next_frame() {
    let mut entities = vec![camera()];
    for id in 2..=51 {
        entities.push(body(id));
    }
    let mut scene = Scene::default();
    for entity in entities {
        scene.entities.insert(entity.id, entity);
    }
    let mut world = World::from_scene(scene, 1);
    for id in 2..=51 {
        world.attach_script(id, "-- ok");
    }
    world.script_time_hook = Some(fake_script_ms(1));

    let mut host = ScriptHost::new().expect("host");
    host.step(&mut world, &InputFrame::default())
        .expect("frame 1");
    let first = world.last_script_frame.clone();
    assert!(first.global_hard);
    assert_eq!(first.ran.len(), 12);
    assert_eq!(first.starved.len(), 38);
    assert_eq!(first.ran, (2..=13).collect::<Vec<_>>());
    assert_eq!(first.starved[0], 14);

    host.step(&mut world, &InputFrame::default())
        .expect("frame 2");
    let second = world.last_script_frame.clone();
    assert_eq!(
        &second.ran[..12],
        &first.starved[..12],
        "GS-EC-26: starved scripts run first next frame"
    );
    assert_eq!(second.ran.len(), 12);
    assert_eq!(second.starved.len(), 38);
}

/// GS-EC-25 — dead id reads are nil/false, no script error.
#[test]
fn dead_id_reads_are_nil_or_false() {
    let mut world = simple_world(vec![body(2), body(3)]);
    world.attach_script(
        2,
        r#"
            local M = {}
            function M.on_update(self, dt)
              local held = "e_000003"
              gs.destroy(held)
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
    assert!(world.script_errors.iter().all(|e| e.entity_id != 2));
}
