use std::time::{Duration, Instant};

use gs_scene::{Camera2D, Entity, Scene, Transform2D};

use super::*;
use crate::schedule::step;
use crate::world::{InputFrame, World};

const TIGHT_LOOP: &str = r#"
        local i = 0
        while true do
            i += 1
        end
    "#;

fn camera(id: u64) -> Entity {
    let mut entity = Entity::new(id, None, 0);
    entity.transform = Some(Transform2D::identity());
    entity.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    entity
}

fn body(id: u64, x: f32, y: f32) -> Entity {
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

fn world_from(entities: Vec<Entity>) -> World {
    let mut scene = Scene::default();
    for entity in entities {
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

fn error_mentions_deadline(err: &ScriptError) -> bool {
    matches!(err, ScriptError::Deadline) || err.to_string().contains(DEADLINE_MESSAGE)
}

#[test]
fn infinite_loop_stopped_by_deadline() {
    let vm = ScriptVm::new().expect("vm");
    let mut world = world_from(vec![body(2, 0.0, 0.0)]);
    let budget = Duration::from_millis(50);
    let started = Instant::now();
    let err = vm
        .exec(&mut world, TIGHT_LOOP, budget)
        .expect_err("infinite loop must fail");
    let elapsed = started.elapsed();

    assert!(
        error_mentions_deadline(&err),
        "expected deadline error, got {err}"
    );
    assert!(
        elapsed < Duration::from_secs(3),
        "deadline must stop the loop in a few seconds, took {elapsed:?}"
    );
    assert!(
        elapsed >= budget,
        "must run at least until the budget, took {elapsed:?}"
    );
    let report = vm.last_report().expect("report");
    assert!(
        report.interrupts > 0,
        "GS-EC-22: real safepoint interrupt must fire"
    );
    assert!(report.cancelled);
    assert_eq!(pos(&world, 2), (0.0, 0.0));
}

#[test]
fn memory_bomb_returns_memory_error_vm_lives() {
    // Production cap is MEMORY_LIMIT_BYTES (64 MiB). A 2 MiB test cap
    // keeps GS-EC-23 fast and non-flaky on Windows debug builds.
    const TEST_LIMIT: usize = 2 * 1024 * 1024;
    let vm = ScriptVm::with_memory_limit(TEST_LIMIT).expect("vm");
    assert_eq!(vm.memory_limit(), TEST_LIMIT);
    let mut world = world_from(vec![body(2, 0.0, 0.0)]);
    let err = vm
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
        "GS-EC-23 expected MemoryError, got {err}"
    );
    let after = vm.used_memory();
    assert!(after > 0, "VM must still report used_memory");
    let ok = vm.exec(
        &mut world,
        "gs.log(\"info\", \"alive\")",
        Duration::from_secs(1),
    );
    assert!(
        ok.is_ok() || matches!(ok, Err(ScriptError::Memory)),
        "VM object must still exist after MemoryError: {ok:?}"
    );
}

#[test]
fn pcall_does_not_swallow_deadline() {
    let vm = ScriptVm::new().expect("vm");
    let mut world = world_from(vec![body(2, 0.0, 0.0)]);
    let err = vm
        .exec(
            &mut world,
            r#"
                    local ok, err = pcall(function()
                        while true do end
                    end)
                    gs.set_pos("e_000002", 1, 1)
                "#,
            Duration::from_millis(50),
        )
        .expect_err("pcall must not let the callback succeed");
    assert!(error_mentions_deadline(&err), "{err}");
    assert!(
        matches!(err, ScriptError::Deadline),
        "GS-EC-24 host cancel flag is the death sentence, got {err}"
    );
    assert_eq!(pos(&world, 2), (0.0, 0.0));
    let report = vm.last_report().expect("report");
    assert!(report.cancelled);
    assert!(report.interrupts > 0);
}

#[test]
fn failed_callback_discards_set_pos() {
    let mut world = world_from(vec![camera(1), body(2, 3.0, 4.0)]);
    world.attach_script(
        2,
        r#"
                gs.set_pos("e_000002", 10, 20)
                error("boom")
            "#,
    );
    step(&mut world, &InputFrame::default()).expect("step");
    assert_eq!(pos(&world, 2), (3.0, 4.0));
    assert!(world
        .script_errors
        .iter()
        .any(|e| e.entity_id == 2 && !e.deadline));
}

#[test]
fn successful_set_pos_commits_to_world() {
    let mut world = world_from(vec![camera(1), body(2, 0.0, 0.0)]);
    world.attach_script(2, r#"gs.set_pos("e_000002", 10, 20)"#);
    step(&mut world, &InputFrame::default()).expect("step");
    assert_eq!(pos(&world, 2), (10.0, 20.0));
    assert!(world.script_errors.is_empty());
    assert_eq!(world.scripts_ran, vec![2]);
}

#[test]
fn global_hard_skips_and_starved_run_next_frame() {
    let mut entities = vec![camera(1)];
    for id in 2..=51 {
        entities.push(body(id, 0.0, 0.0));
    }
    let mut world = world_from(entities);
    for id in 2..=51 {
        world.attach_script(id, "-- ok");
    }
    world.script_time_hook = Some(ScriptTimeHook {
        advance_per_script: Duration::from_millis(1),
    });

    step(&mut world, &InputFrame::default()).expect("frame 1");
    let first = world.last_script_frame.clone();
    assert!(
        first.global_hard,
        "50 scripts × 1ms fake elapsed must hit 12ms global hard"
    );
    assert_eq!(first.ran.len(), 12);
    assert_eq!(first.starved.len(), 38);
    assert_eq!(first.ran, (2..=13).collect::<Vec<_>>());
    assert_eq!(first.starved[0], 14);
    assert_eq!(world.starved_scripts, first.starved);

    step(&mut world, &InputFrame::default()).expect("frame 2");
    let second = world.last_script_frame.clone();
    assert_eq!(
        &second.ran[..12],
        &first.starved[..12],
        "GS-EC-26: starved scripts run first next frame"
    );
    assert!(second.global_hard);
    assert_eq!(second.ran.len(), 12);
    assert_eq!(second.starved.len(), 38);
}

#[test]
fn script_environments_are_isolated() {
    let mut world = world_from(vec![camera(1), body(2, 0.0, 0.0), body(3, 0.0, 0.0)]);
    world.attach_script(2, "foo = 123");
    world.attach_script(
        3,
        r#"
                if foo ~= nil then
                    gs.set_pos("e_000003", 7, 7)
                else
                    gs.set_pos("e_000003", 1, 1)
                end
            "#,
    );
    step(&mut world, &InputFrame::default()).expect("step");
    assert_eq!(
        pos(&world, 3),
        (1.0, 1.0),
        "script B must not see script A's global"
    );
    assert_eq!(pos(&world, 2), (0.0, 0.0));
}
