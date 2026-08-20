//! Product Snake: load `games/snake` from disk and drive it with ScriptHost.

use std::collections::BTreeMap;
use std::path::PathBuf;

use gs_runtime_core::{step_with_host, InputFrame, ScriptHost, World};

const HEAD: u64 = 10;
const FOOD: u64 = 11;
const CAMERA: u64 = 1;
const BOARD: u64 = 2;

fn snake_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../games/snake")
}

fn load_snake() -> World {
    let root = snake_root();
    let scene = root.join("scenes/main.gscene.json");
    let mut world = World::from_scene_path(&scene, 1).expect("games/snake scene");
    world
        .load_script_sources(&root)
        .expect("load scripts from games/snake");
    assert!(
        world
            .attached_scripts
            .get(&HEAD)
            .is_some_and(|s| s.contains("return M") && s.contains("gs.action(\"move_x\")")),
        "snake.luau must be read from disk"
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

fn right() -> InputFrame {
    actions(&[("move_x", 1.0), ("move_y", 0.0)])
}

fn pose(world: &World, id: u64) -> (f32, f32) {
    let t = world
        .entities
        .get(&id)
        .and_then(|e| e.transform.as_ref())
        .expect("transform");
    (t.x, t.y)
}

fn step_host(world: &mut World, host: &mut ScriptHost, input: &InputFrame) {
    step_with_host(world, input, host).expect("step_with_host");
    assert!(
        world.script_errors.is_empty(),
        "script errors: {:?}",
        world.script_errors
    );
}

fn place_food_at(world: &mut World, x: f32, y: f32) {
    let food = world.entities.get_mut(&FOOD).expect("food entity");
    let t = food.transform.as_mut().expect("food transform");
    t.x = x;
    t.y = y;
}

#[test]
fn scene_and_script_load_from_disk() {
    let root = snake_root();
    let source = std::fs::read_to_string(root.join("scripts/snake.luau"))
        .expect("games/snake/scripts/snake.luau");
    assert!(source.contains("--!strict"));
    assert!(source.contains("return M"));
    assert!(source.contains("FoodEaten"));
    assert!(source.contains("SnakeDied"));

    let project_text =
        std::fs::read_to_string(root.join("project.json")).expect("games/snake/project.json");
    let project: serde_json::Value =
        serde_json::from_str(&project_text).expect("project.json json");
    assert!(
        project["next_entity"].as_u64().expect("next_entity") >= 20,
        "next_entity must be >= 20"
    );
    assert_eq!(project["schema_version"].as_u64(), Some(1));

    let inputmap_text =
        std::fs::read_to_string(root.join("inputmap.json")).expect("games/snake/inputmap.json");
    assert!(inputmap_text.contains("move_x"));
    assert!(inputmap_text.contains("move_y"));

    let world = load_snake();
    assert_eq!(
        world.script_bindings.get(&HEAD).map(|b| b.file.as_str()),
        Some("scripts/snake.luau")
    );
    assert!(world.entities.contains_key(&HEAD), "head e_000010");
    assert!(world.entities.contains_key(&FOOD), "food e_000011");
    assert!(
        world
            .entities
            .get(&CAMERA)
            .and_then(|e| e.extra.camera.as_ref())
            .is_some_and(|c| c.active && (c.ortho_height - 18.0).abs() < 0.01),
        "active camera ortho_height ~18"
    );
    assert!(
        world
            .entities
            .get(&BOARD)
            .and_then(|e| e.extra.tilemap.as_ref())
            .is_some(),
        "board tilemap"
    );
    let tags = world
        .entities
        .get(&HEAD)
        .and_then(|e| e.tags.as_ref())
        .expect("head tags");
    assert!(tags.values.iter().any(|t| t == "head"));
}

#[test]
fn move_x_increases_head_x() {
    let mut world = load_snake();
    let mut host = ScriptHost::new().expect("host");
    let (x0, y0) = pose(&world, HEAD);
    let walk = right();
    for _ in 0..20 {
        step_host(&mut world, &mut host, &walk);
    }
    let (x1, y1) = pose(&world, HEAD);
    assert!(x1 > x0 + 0.9, "move_x=1 should move ≥1 cell ({x0} -> {x1})");
    assert!(
        (y1 - y0).abs() < 0.01,
        "heading right must keep y ({y0} -> {y1})"
    );
}

#[test]
fn eat_food_on_next_cell_emits_food_eaten() {
    let mut world = load_snake();
    let (hx, hy) = pose(&world, HEAD);
    place_food_at(&mut world, hx + 1.0, hy);

    let mut host = ScriptHost::new().expect("host");
    let walk = right();
    for _ in 0..20 {
        step_host(&mut world, &mut host, &walk);
    }

    let eaten = world
        .play_events
        .iter()
        .find(|e| e.name == "FoodEaten")
        .expect("FoodEaten");
    assert_eq!(eaten.data["food"], "e_000011");
    let (fx, fy) = pose(&world, FOOD);
    assert!(
        (fx - 1.0).abs() < 0.01 && (fy - 1.0).abs() < 0.01,
        "food should relocate to first free cell (1,1), got ({fx}, {fy})"
    );
}

#[test]
fn drive_into_wall_emits_snake_died() {
    let mut world = load_snake();
    let mut host = ScriptHost::new().expect("host");
    let walk = right();
    for _ in 0..120 {
        step_host(&mut world, &mut host, &walk);
    }

    assert!(
        world.play_events.iter().any(|e| e.name == "SnakeDied"),
        "SnakeDied after driving into the right wall"
    );
    let (x_dead, y_dead) = pose(&world, HEAD);
    for _ in 0..12 {
        step_host(&mut world, &mut host, &walk);
    }
    let (x1, y1) = pose(&world, HEAD);
    assert!(
        (x1 - x_dead).abs() < 0.01 && (y1 - y_dead).abs() < 0.01,
        "dead snake must stop moving ({x_dead},{y_dead}) -> ({x1},{y1})"
    );
    assert!(
        x_dead < 15.0,
        "head should stop before entering the wall cell, x={x_dead}"
    );
}
