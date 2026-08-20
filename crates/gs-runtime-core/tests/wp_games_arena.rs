//! Load `games/arena-brawl` from disk and drive it with ScriptHost + PhysicsHost.

use std::collections::BTreeMap;
use std::path::PathBuf;

use gs_runtime_core::{step_with_hosts, InputFrame, PhysicsHost, ScriptHost, World};

const FIGHTER_A: u64 = 20;
const FIGHTER_B: u64 = 21;

fn arena_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../games/arena-brawl")
}

fn load_arena() -> World {
    let root = arena_root();
    let scene = root.join("scenes/main.gscene.json");
    let mut world = World::from_scene_path(&scene, 1).expect("games/arena-brawl scene");
    world
        .load_script_sources(&root)
        .expect("load scripts from games/arena-brawl");
    let source = std::fs::read_to_string(root.join("scripts/fighter.luau"))
        .expect("games/arena-brawl/scripts/fighter.luau");
    assert!(source.contains("--!strict"));
    assert!(source.contains("return M"));
    assert!(source.contains("Hit"));
    assert!(source.contains("FighterDown"));
    assert_eq!(
        world
            .script_bindings
            .get(&FIGHTER_A)
            .map(|b| b.file.as_str()),
        Some("scripts/fighter.luau")
    );
    assert_eq!(
        world
            .script_bindings
            .get(&FIGHTER_B)
            .map(|b| b.file.as_str()),
        Some("scripts/fighter.luau")
    );
    assert!(
        world
            .attached_scripts
            .get(&FIGHTER_A)
            .is_some_and(|s| s.contains("return M") && s.contains("attack_")),
        "fighter.luau must be read from disk"
    );
    world
}

fn actions(pairs: &[(&str, f32)]) -> InputFrame {
    let mut map = BTreeMap::new();
    for (name, value) in pairs {
        map.insert((*name).to_string(), *value);
    }
    InputFrame { actions: map }
}

fn idle() -> InputFrame {
    actions(&[
        ("move_x_p1", 0.0),
        ("jump_p1", 0.0),
        ("attack_p1", 0.0),
        ("move_x_p2", 0.0),
        ("jump_p2", 0.0),
        ("attack_p2", 0.0),
    ])
}

fn attack_pulse() -> InputFrame {
    actions(&[
        ("move_x_p1", 0.0),
        ("jump_p1", 0.0),
        ("attack_p1", 1.0),
        ("move_x_p2", 0.0),
        ("jump_p2", 0.0),
        ("attack_p2", 0.0),
    ])
}

fn pose(world: &World, id: u64) -> (f32, f32) {
    let t = world
        .entities
        .get(&id)
        .and_then(|e| e.transform.as_ref())
        .expect("transform");
    (t.x, t.y)
}

fn set_pose(world: &mut World, id: u64, x: f32, y: f32) {
    let t = world
        .entities
        .get_mut(&id)
        .and_then(|e| e.transform.as_mut())
        .expect("transform");
    t.x = x;
    t.y = y;
}

fn step_hosts(
    world: &mut World,
    host: &mut ScriptHost,
    phys: &mut PhysicsHost,
    input: &InputFrame,
) {
    step_with_hosts(world, input, host, phys).expect("step_with_hosts");
    assert!(
        world.script_errors.is_empty(),
        "script errors: {:?}",
        world.script_errors
    );
}

fn settle(world: &mut World, host: &mut ScriptHost, phys: &mut PhysicsHost, frames: u32) {
    let input = idle();
    for _ in 0..frames {
        step_hosts(world, host, phys, &input);
    }
}

fn rest_y(world: &World, id: u64) -> f32 {
    let y = pose(world, id).1;
    y.clamp(1.2, 1.8)
}

fn overlap_then_ready(world: &mut World, host: &mut ScriptHost, phys: &mut PhysicsHost) -> bool {
    const TRIES: &[(f32, f32)] = &[(4.0, 4.55), (4.1, 4.45), (4.2, 4.35), (4.25, 4.25)];
    let y = rest_y(world, FIGHTER_A)
        .max(rest_y(world, FIGHTER_B))
        .clamp(1.2, 1.8);
    for &(ax, bx) in TRIES {
        set_pose(world, FIGHTER_A, ax, y);
        set_pose(world, FIGHTER_B, bx, y);
        phys.set_linear_velocity(FIGHTER_A, 0.0, 0.0);
        phys.set_linear_velocity(FIGHTER_B, 0.0, 0.0);
        step_hosts(world, host, phys, &idle());
        if phys.physics_overlaps(FIGHTER_A).contains(&FIGHTER_B) {
            return true;
        }
    }
    false
}

fn hp_of(host: &ScriptHost, id: u64) -> Option<f64> {
    host.state_json(id)
        .and_then(|s| s.get("hp").cloned())
        .and_then(|v| v.as_f64())
}

#[test]
fn both_fighters_rest_on_floor() {
    let mut world = load_arena();
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 30);

    let (ax, ay) = pose(&world, FIGHTER_A);
    let (bx, by) = pose(&world, FIGHTER_B);
    assert!(
        ay > 0.8 && ay < 2.2,
        "fighter A should rest on the floor (x={ax} y={ay})"
    );
    assert!(
        by > 0.8 && by < 2.2,
        "fighter B should rest on the floor (x={bx} y={by})"
    );
    assert!(
        world.entities.contains_key(&FIGHTER_A) && world.entities.contains_key(&FIGHTER_B),
        "both fighters must still exist"
    );
}

#[test]
fn attack_while_overlapping_emits_hit_and_knocks_back() {
    let mut world = load_arena();
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 30);

    assert!(
        overlap_then_ready(&mut world, &mut host, &mut phys),
        "fighters must contact before attack"
    );

    let (bx0, by0) = pose(&world, FIGHTER_B);
    let hp0 = hp_of(&host, FIGHTER_B).unwrap_or(3.0);
    step_hosts(&mut world, &mut host, &mut phys, &attack_pulse());
    let idle = idle();
    for _ in 0..4 {
        step_hosts(&mut world, &mut host, &mut phys, &idle);
    }

    let hit = world
        .play_events
        .iter()
        .find(|e| e.name == "Hit")
        .expect("Hit");
    assert_eq!(hit.data["by"], "e_000020");
    assert_eq!(hit.data["target"], "e_000021");

    let (bx1, by1) = pose(&world, FIGHTER_B);
    let hp1 = hp_of(&host, FIGHTER_B);
    let moved = (bx1 - bx0).abs() > 0.04 || (by1 - by0).abs() > 0.04;
    let hp_dropped = hp1.is_some_and(|h| h < hp0);
    assert!(
        moved || hp_dropped,
        "B should be knocked or lose hp (pos {bx0},{by0} -> {bx1},{by1} hp={hp1:?})"
    );
}

#[test]
fn three_hits_emits_fighter_down_and_removes_one() {
    let mut world = load_arena();
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 30);

    for n in 1..=3 {
        assert!(
            world.entities.contains_key(&FIGHTER_A) && world.entities.contains_key(&FIGHTER_B),
            "both fighters must exist before hit {n}"
        );
        assert!(
            overlap_then_ready(&mut world, &mut host, &mut phys),
            "fighters must contact before hit {n}"
        );
        step_hosts(&mut world, &mut host, &mut phys, &attack_pulse());
        step_hosts(&mut world, &mut host, &mut phys, &idle());
    }

    assert!(
        world.play_events.iter().any(|e| e.name == "FighterDown"),
        "three hits must emit FighterDown: {:?}",
        world.play_events
    );
    let a_alive = world.entities.contains_key(&FIGHTER_A);
    let b_alive = world.entities.contains_key(&FIGHTER_B);
    assert!(
        a_alive != b_alive,
        "exactly one fighter should remain (A={a_alive} B={b_alive})"
    );
}
