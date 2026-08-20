//! Load `games/scrap-yard` and drive split-control fighters.

use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::{Mutex, MutexGuard, OnceLock};

use gs_runtime_core::{step_with_hosts, InputFrame, PhysicsHost, ScriptHost, World};
use serde_json::json;

const VELA: u64 = 20;
const ROOK: u64 = 21;
const ARENA_W: f32 = 40.0;
const ARENA_H: f32 = 22.0;

fn scrap_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../games/scrap-yard")
}

/// Script deadlines are wall-clock (4ms). Parallel cargo-test threads on a
/// busy machine starve the VM and flake `deadline exceeded`.
fn serial() -> MutexGuard<'static, ()> {
    static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    LOCK.get_or_init(|| Mutex::new(()))
        .lock()
        .unwrap_or_else(|e| e.into_inner())
}

fn load_scrap() -> World {
    let root = scrap_root();
    let scene = root.join("scenes/main.gscene.json");
    let mut world = World::from_scene_path(&scene, 1).expect("games/scrap-yard scene");
    world
        .load_script_sources(&root)
        .expect("load scripts from games/scrap-yard");
    let source = std::fs::read_to_string(root.join("scripts/fighter.luau"))
        .expect("games/scrap-yard/scripts/fighter.luau");
    assert!(source.contains("--!strict"));
    assert!(source.contains("return M"));
    assert!(source.contains("act(self, \"move_x\")"));
    assert!(
        !source.to_ascii_lowercase().contains("superfighter"),
        "original game must not name Superfighters in scripts"
    );
    assert!(
        !world.entities.contains_key(&30) && !world.entities.contains_key(&31),
        "floating head entities e_000030/e_000031 must be gone"
    );
    assert_eq!(
        world.script_bindings.get(&VELA).map(|b| b.file.as_str()),
        Some("scripts/fighter.luau")
    );
    assert_eq!(
        world.script_bindings.get(&ROOK).map(|b| b.file.as_str()),
        Some("scripts/fighter.luau")
    );
    world
}

fn disable_ai(world: &mut World, id: u64) {
    if let Some(script) = world
        .entities
        .get_mut(&id)
        .and_then(|e| e.extra.script.as_mut())
    {
        script.props.insert("ai".into(), json!(false));
    }
    if let Some(binding) = world.script_bindings.get_mut(&id) {
        binding.props.insert("ai".into(), json!(false));
    }
}

fn set_pose(world: &mut World, id: u64, x: f32, y: f32) {
    if let Some(t) = world
        .entities
        .get_mut(&id)
        .and_then(|e| e.transform.as_mut())
    {
        t.x = x;
        t.y = y;
    }
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
        ("crouch_p1", 0.0),
        ("melee_p1", 0.0),
        ("shoot_p1", 0.0),
        ("grenade_p1", 0.0),
        ("power_p1", 0.0),
        ("move_x_p2", 0.0),
        ("jump_p2", 0.0),
        ("crouch_p2", 0.0),
        ("melee_p2", 0.0),
        ("shoot_p2", 0.0),
        ("grenade_p2", 0.0),
        ("power_p2", 0.0),
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
fn both_fighters_rest_on_floor() {
    let _serial = serial();
    let mut world = load_scrap();
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 40);

    let (ax, ay) = pose(&world, VELA);
    let (bx, by) = pose(&world, ROOK);
    assert!(
        ay > 0.8 && ay < 2.6,
        "Vela should rest on the floor (x={ax} y={ay})"
    );
    assert!(
        by > 0.8 && by < 2.6,
        "Rook should rest on the floor (x={bx} y={by})"
    );
    assert!(
        world.entities.contains_key(&VELA) && world.entities.contains_key(&ROOK),
        "both fighters must still exist"
    );
}

#[test]
fn p2_walk_does_not_move_p1() {
    let _serial = serial();
    let mut world = load_scrap();
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 30);

    let (ax0, _) = pose(&world, VELA);
    let (bx0, _) = pose(&world, ROOK);
    let walk_p2 = actions(&[
        ("move_x_p1", 0.0),
        ("move_x_p2", -1.0),
        ("jump_p1", 0.0),
        ("jump_p2", 0.0),
        ("crouch_p1", 1.0),
        ("crouch_p2", 0.0),
        ("melee_p1", 0.0),
        ("melee_p2", 0.0),
        ("shoot_p1", 0.0),
        ("shoot_p2", 0.0),
        ("grenade_p1", 0.0),
        ("grenade_p2", 0.0),
        ("power_p1", 0.0),
        ("power_p2", 0.0),
    ]);
    for _ in 0..20 {
        step_hosts(&mut world, &mut host, &mut phys, &walk_p2);
    }
    let (ax1, _) = pose(&world, VELA);
    let (bx1, _) = pose(&world, ROOK);
    assert!(
        (ax1 - ax0).abs() < 0.35,
        "P1/Vela must stay put when only P2 walks ( {ax0} -> {ax1} )"
    );
    assert!(
        bx1 < bx0 - 0.25,
        "P2/Rook should walk left ( {bx0} -> {bx1} )"
    );
}

#[test]
fn melee_p2_on_overlap_emits_hit() {
    let _serial = serial();
    let mut world = load_scrap();
    disable_ai(&mut world, VELA);
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 30);

    if let Some(t) = world
        .entities
        .get_mut(&VELA)
        .and_then(|e| e.transform.as_mut())
    {
        t.x = 12.0;
        t.y = 1.6;
    }
    if let Some(t) = world
        .entities
        .get_mut(&ROOK)
        .and_then(|e| e.transform.as_mut())
    {
        t.x = 12.7;
        t.y = 1.6;
    }
    phys.set_linear_velocity(VELA, 0.0, 0.0);
    phys.set_linear_velocity(ROOK, 0.0, 0.0);
    step_hosts(&mut world, &mut host, &mut phys, &idle());

    let punch = actions(&[
        ("move_x_p1", 0.0),
        ("move_x_p2", 0.0),
        ("jump_p1", 0.0),
        ("jump_p2", 0.0),
        ("crouch_p1", 0.0),
        ("crouch_p2", 0.0),
        ("melee_p1", 0.0),
        ("melee_p2", 1.0),
        ("shoot_p1", 0.0),
        ("shoot_p2", 0.0),
        ("grenade_p1", 0.0),
        ("grenade_p2", 0.0),
        ("power_p1", 0.0),
        ("power_p2", 0.0),
    ]);
    step_hosts(&mut world, &mut host, &mut phys, &punch);
    for _ in 0..4 {
        step_hosts(&mut world, &mut host, &mut phys, &idle());
    }
    assert!(
        world.play_events.iter().any(|e| e.name == "Hit"),
        "melee on overlap must emit Hit: {:?}",
        world.play_events
    );
    let fill = world
        .entities
        .get(&41)
        .and_then(|e| e.transform.as_ref())
        .map(|t| t.sx)
        .unwrap_or(1.5);
    assert!(
        fill < 1.4,
        "Vela hp fill must shrink after a hit (sx={fill})"
    );
}

#[test]
fn vela_jump_reaches_low_catwalk() {
    let _serial = serial();
    let mut world = load_scrap();
    disable_ai(&mut world, VELA);
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 25);

    // Left tower step (y=3, top 4) up to the low catwalk (y=5, top 6).
    set_pose(&mut world, VELA, 4.0, 4.25);
    phys.set_linear_velocity(VELA, 0.0, 0.0);
    let hop = actions(&[
        ("move_x_p1", 1.0),
        ("jump_p1", 1.0),
        ("move_x_p2", 0.0),
        ("jump_p2", 0.0),
        ("crouch_p1", 0.0),
        ("crouch_p2", 0.0),
        ("melee_p1", 0.0),
        ("melee_p2", 0.0),
        ("shoot_p1", 0.0),
        ("shoot_p2", 0.0),
        ("grenade_p1", 0.0),
        ("grenade_p2", 0.0),
        ("power_p1", 0.0),
        ("power_p2", 0.0),
    ]);
    for _ in 0..40 {
        step_hosts(&mut world, &mut host, &mut phys, &hop);
    }
    settle(&mut world, &mut host, &mut phys, 55);
    let (x, y) = pose(&world, VELA);
    assert!(
        y > 5.5 && y < 8.0 && x > 4.5 && x < 15.5,
        "Vela should land on the low catwalk (x={x} y={y})"
    );
}

#[test]
fn both_fighters_settle_inside_arena() {
    let _serial = serial();
    let mut world = load_scrap();
    disable_ai(&mut world, VELA);
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 60);

    for id in [VELA, ROOK] {
        let (x, y) = pose(&world, id);
        assert!(
            y > 0.8 && y < 2.6,
            "fighter {id} should rest on the floor (x={x} y={y})"
        );
        assert!(
            x > 0.5 && x < ARENA_W - 0.5 && y > 0.0 && y < ARENA_H,
            "fighter {id} left the arena (x={x} y={y})"
        );
    }
    assert!(world.entities.contains_key(&VELA) && world.entities.contains_key(&ROOK));
}

#[test]
fn p2_input_moves_only_rook_when_ai_off() {
    let _serial = serial();
    let mut world = load_scrap();
    disable_ai(&mut world, VELA);
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 30);

    let (ax0, _) = pose(&world, VELA);
    let (bx0, _) = pose(&world, ROOK);
    let walk_p2 = actions(&[
        ("move_x_p1", 0.0),
        ("move_x_p2", -1.0),
        ("jump_p1", 0.0),
        ("jump_p2", 0.0),
        ("crouch_p1", 0.0),
        ("crouch_p2", 0.0),
        ("melee_p1", 0.0),
        ("melee_p2", 0.0),
        ("shoot_p1", 0.0),
        ("shoot_p2", 0.0),
        ("grenade_p1", 0.0),
        ("grenade_p2", 0.0),
        ("power_p1", 0.0),
        ("power_p2", 0.0),
    ]);
    for _ in 0..20 {
        step_hosts(&mut world, &mut host, &mut phys, &walk_p2);
    }
    let (ax1, _) = pose(&world, VELA);
    let (bx1, _) = pose(&world, ROOK);
    assert!(
        (ax1 - ax0).abs() < 0.35,
        "Vela x must barely change with AI off ( {ax0} -> {ax1} )"
    );
    assert!(
        bx1 < bx0 - 0.25,
        "Rook should walk left on P2 input ( {bx0} -> {bx1} )"
    );
}

#[test]
fn coyote_time_allows_jump_after_leaving_ledge() {
    let _serial = serial();
    let mut world = load_scrap();
    disable_ai(&mut world, VELA);
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 20);

    set_pose(&mut world, ROOK, 14.0, 6.25);
    phys.set_linear_velocity(ROOK, 0.0, 0.0);
    settle(&mut world, &mut host, &mut phys, 12);

    let walk = actions(&[
        ("move_x_p2", 1.0),
        ("jump_p2", 0.0),
        ("move_x_p1", 0.0),
        ("jump_p1", 0.0),
        ("crouch_p1", 0.0),
        ("crouch_p2", 0.0),
        ("melee_p1", 0.0),
        ("melee_p2", 0.0),
        ("shoot_p1", 0.0),
        ("shoot_p2", 0.0),
        ("grenade_p1", 0.0),
        ("grenade_p2", 0.0),
        ("power_p1", 0.0),
        ("power_p2", 0.0),
    ]);
    let mut left_ledge = false;
    for _ in 0..40 {
        step_hosts(&mut world, &mut host, &mut phys, &walk);
        let (x, _y) = pose(&world, ROOK);
        if x > 15.25 {
            left_ledge = true;
            break;
        }
    }
    assert!(left_ledge, "Rook should walk off the low catwalk");

    for _ in 0..2 {
        step_hosts(&mut world, &mut host, &mut phys, &walk);
    }
    let (_x0, y0) = pose(&world, ROOK);
    let hop = actions(&[
        ("move_x_p2", 1.0),
        ("jump_p2", 1.0),
        ("move_x_p1", 0.0),
        ("jump_p1", 0.0),
        ("crouch_p1", 0.0),
        ("crouch_p2", 0.0),
        ("melee_p1", 0.0),
        ("melee_p2", 0.0),
        ("shoot_p1", 0.0),
        ("shoot_p2", 0.0),
        ("grenade_p1", 0.0),
        ("grenade_p2", 0.0),
        ("power_p1", 0.0),
        ("power_p2", 0.0),
    ]);
    step_hosts(&mut world, &mut host, &mut phys, &hop);
    for _ in 0..10 {
        step_hosts(&mut world, &mut host, &mut phys, &hop);
    }
    let (_x1, y1) = pose(&world, ROOK);
    assert!(
        y1 > y0 + 0.8,
        "coyote jump should gain height ({y0} -> {y1})"
    );
}

fn jump_apex(hold_frames: u32) -> f32 {
    let mut world = load_scrap();
    disable_ai(&mut world, VELA);
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 25);
    // Gap between low catwalks (ends x=15, next x=18) and west of the dais (x=17).
    // Mid catwalk at y=10 is high enough that hold vs tap still diverge.
    set_pose(&mut world, ROOK, 16.0, 1.25);
    phys.set_linear_velocity(ROOK, 0.0, 0.0);
    settle(&mut world, &mut host, &mut phys, 8);

    let press = actions(&[
        ("move_x_p2", 0.0),
        ("jump_p2", 1.0),
        ("move_x_p1", 0.0),
        ("jump_p1", 0.0),
        ("crouch_p1", 0.0),
        ("crouch_p2", 0.0),
        ("melee_p1", 0.0),
        ("melee_p2", 0.0),
        ("shoot_p1", 0.0),
        ("shoot_p2", 0.0),
        ("grenade_p1", 0.0),
        ("grenade_p2", 0.0),
        ("power_p1", 0.0),
        ("power_p2", 0.0),
    ]);
    let mut apex = pose(&world, ROOK).1;
    for i in 0..50 {
        let input = if i < hold_frames { &press } else { &idle() };
        step_hosts(&mut world, &mut host, &mut phys, input);
        let y = pose(&world, ROOK).1;
        if y > apex {
            apex = y;
        }
    }
    apex
}

#[test]
fn variable_jump_hold_reaches_higher_apex() {
    let _serial = serial();
    let tap = jump_apex(1);
    let hold = jump_apex(24);
    assert!(
        hold > tap + 0.75,
        "held jump must beat a tap ({hold} vs {tap})"
    );
}

#[test]
fn hitstun_ignores_input_for_several_frames() {
    let _serial = serial();
    let mut world = load_scrap();
    disable_ai(&mut world, VELA);
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 25);

    world.queue_script_event(ROOK, "Hit", json!({ "target": "e_000021", "amount": 1 }));
    step_hosts(&mut world, &mut host, &mut phys, &idle());

    let (x0, _) = pose(&world, ROOK);
    let walk = actions(&[
        ("move_x_p2", -1.0),
        ("jump_p2", 0.0),
        ("move_x_p1", 0.0),
        ("jump_p1", 0.0),
        ("crouch_p1", 0.0),
        ("crouch_p2", 0.0),
        ("melee_p1", 0.0),
        ("melee_p2", 0.0),
        ("shoot_p1", 0.0),
        ("shoot_p2", 0.0),
        ("grenade_p1", 0.0),
        ("grenade_p2", 0.0),
        ("power_p1", 0.0),
        ("power_p2", 0.0),
    ]);
    for _ in 0..8 {
        step_hosts(&mut world, &mut host, &mut phys, &walk);
    }
    let (x1, _) = pose(&world, ROOK);
    assert!(
        (x1 - x0).abs() < 0.35,
        "hitstun must ignore walk input ({x0} -> {x1})"
    );

    for _ in 0..10 {
        step_hosts(&mut world, &mut host, &mut phys, &idle());
    }
    let (x2, _) = pose(&world, ROOK);
    for _ in 0..20 {
        step_hosts(&mut world, &mut host, &mut phys, &walk);
    }
    let (x3, _) = pose(&world, ROOK);
    assert!(
        x3 < x2 - 0.25,
        "after hitstun Rook should walk again ({x2} -> {x3})"
    );
}

#[test]
fn fall_out_of_arena_respawns() {
    let _serial = serial();
    let mut world = load_scrap();
    disable_ai(&mut world, VELA);
    let mut host = ScriptHost::new().expect("host");
    let mut phys = PhysicsHost::new();
    settle(&mut world, &mut host, &mut phys, 20);

    set_pose(&mut world, ROOK, 20.0, -4.0);
    phys.set_linear_velocity(ROOK, 0.0, -8.0);
    for _ in 0..20 {
        step_hosts(&mut world, &mut host, &mut phys, &idle());
        if !world.entities.contains_key(&ROOK) {
            break;
        }
        let y = pose(&world, ROOK).1;
        if y > 0.5 {
            break;
        }
    }
    assert!(
        world.entities.contains_key(&ROOK),
        "fallen fighter should respawn, not vanish forever"
    );
    let (x, y) = pose(&world, ROOK);
    assert!(
        y > 0.5 && y < ARENA_H && x > 0.0 && x < ARENA_W,
        "respawn must return Rook to the arena (x={x} y={y})"
    );
}
