//! WP-M4-4 slice: load `templates/2d-platformer` and drive it with ScriptHost +
//! PhysicsHost (not ephemeral `step`).

use std::collections::BTreeMap;
use std::path::PathBuf;

use gs_runtime_core::{step_with_hosts, InputFrame, PhysicsHost, ScriptHost, World};

const PLAYER: u64 = 3;
const COIN: u64 = 4;

fn platformer_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../templates/2d-platformer")
}

fn load_platformer() -> World {
    let root = platformer_root();
    let scene = root.join("scenes/main.gscene.json");
    let mut world = World::from_scene_path(&scene, 1).expect("templates/2d-platformer scene");
    world
        .load_script_sources(&root)
        .expect("load scripts from templates/2d-platformer");
    assert!(
        world
            .attached_scripts
            .get(&PLAYER)
            .is_some_and(|s| s.contains("return M") && s.contains("gs.action(\"move_x\")")),
        "player_move.luau must be read from disk"
    );
    assert!(
        world
            .attached_scripts
            .get(&COIN)
            .is_some_and(|s| s.contains("CoinPicked") && s.contains("return M")),
        "coin.luau must be read from disk"
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
    actions(&[("move_x", 0.0), ("jump", 0.0)])
}

fn pose(world: &World, id: u64) -> (f32, f32) {
    let t = world
        .entities
        .get(&id)
        .and_then(|e| e.transform.as_ref())
        .expect("transform");
    (t.x, t.y)
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

#[test]
fn scripts_are_loaded_from_templates_on_disk() {
    let root = platformer_root();
    let player = std::fs::read_to_string(root.join("scripts/player_move.luau"))
        .expect("templates/2d-platformer/scripts/player_move.luau");
    let coin = std::fs::read_to_string(root.join("scripts/coin.luau"))
        .expect("templates/2d-platformer/scripts/coin.luau");
    assert!(player.contains("--!strict"));
    assert!(player.contains("return M"));
    assert!(coin.contains("--!strict"));
    assert!(coin.contains("CoinPicked"));

    let shared = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../templates/scripts");
    let shared_player = std::fs::read_to_string(shared.join("player_move.luau"))
        .expect("templates/scripts/player_move.luau");
    let shared_coin =
        std::fs::read_to_string(shared.join("coin.luau")).expect("templates/scripts/coin.luau");
    assert_eq!(
        player.replace("\r\n", "\n"),
        shared_player.replace("\r\n", "\n")
    );
    assert_eq!(
        coin.replace("\r\n", "\n"),
        shared_coin.replace("\r\n", "\n")
    );

    let world = load_platformer();
    assert_eq!(
        world.script_bindings.get(&PLAYER).map(|b| b.file.as_str()),
        Some("scripts/player_move.luau")
    );
    assert_eq!(
        world.script_bindings.get(&COIN).map(|b| b.file.as_str()),
        Some("scripts/coin.luau")
    );
}

#[test]
fn player_rests_on_solid_tiles_without_input() {
    let mut world = load_platformer();
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 30);

    let (x, y) = pose(&world, PLAYER);
    assert!(
        y > 0.8 && y < 2.2,
        "player should rest on the y=0 tile row, not fall through (x={x} y={y})"
    );
    assert!(
        !world.play_events.iter().any(|e| e.name == "CoinPicked"),
        "idle settle must not collect the coin"
    );
}

#[test]
fn move_x_increases_player_x() {
    let mut world = load_platformer();
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 30);

    let (x0, y0) = pose(&world, PLAYER);
    let walk = actions(&[("move_x", 1.0), ("jump", 0.0)]);
    for _ in 0..20 {
        step_hosts(&mut world, &mut host, &mut phys, &walk);
    }
    let (x1, y1) = pose(&world, PLAYER);
    assert!(x1 > x0 + 0.3, "move_x=1 should increase x ({x0} -> {x1})");
    assert!(
        y1 > 0.8 && y1 < 2.5,
        "walking should stay on the floor (y0={y0} y1={y1})"
    );
}

#[test]
fn walk_into_coin_emits_coin_picked_and_destroys() {
    let mut world = load_platformer();
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 30);

    let walk = actions(&[("move_x", 1.0), ("jump", 0.0)]);
    for _ in 0..20 {
        step_hosts(&mut world, &mut host, &mut phys, &walk);
    }
    settle(&mut world, &mut host, &mut phys, 3);

    let picked = world
        .play_events
        .iter()
        .find(|e| e.name == "CoinPicked")
        .expect("CoinPicked");
    assert_eq!(picked.data["coin"], "e_000004");
    assert!(
        !world.entities.contains_key(&COIN),
        "coin entity must be gone after CoinPicked"
    );
}

#[test]
fn jump_raises_player_y_when_grounded() {
    let mut world = load_platformer();
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 30);

    let (_x0, y0) = pose(&world, PLAYER);
    assert!(y0 > 0.8 && y0 < 2.2, "pre-jump rest y={y0}");

    step_hosts(
        &mut world,
        &mut host,
        &mut phys,
        &actions(&[("move_x", 0.0), ("jump", 1.0)]),
    );
    let idle = idle();
    for _ in 0..8 {
        step_hosts(&mut world, &mut host, &mut phys, &idle);
    }
    let (_x1, y1) = pose(&world, PLAYER);
    assert!(
        y1 > y0 + 0.15,
        "jump should raise y vs pre-jump (y0={y0} y1={y1})"
    );
}
