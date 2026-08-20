//! Keyboard → inputmap actions while Play is running (MASTER 6.4 / T3.4).

use std::collections::BTreeSet;

use eframe::egui;
use serde_json::{json, Value};

/// Cover upcoming 60 Hz sim steps. Editor polls ~50 ms; `input.inject`
/// `frame_offset: 0` is one pulse then zero (MASTER 6.4). Hold must span.
pub const HOLD_FRAMES: u32 = 8;

pub fn normalize_key_name(raw: &str) -> String {
    match raw.trim() {
        "Left" | "ArrowLeft" => "Left".into(),
        "Right" | "ArrowRight" => "Right".into(),
        "Up" | "ArrowUp" => "Up".into(),
        "Down" | "ArrowDown" => "Down".into(),
        "Space" | "Spacebar" => "Space".into(),
        "," | "Comma" => "Comma".into(),
        "." | "Period" => "Period".into(),
        other if other.len() == 1 => other.to_ascii_uppercase(),
        other => other.to_string(),
    }
}

pub fn actions_from_held(map: &Value, held: &BTreeSet<String>) -> Vec<Value> {
    let Some(arr) = map.get("actions").and_then(Value::as_array) else {
        return Vec::new();
    };
    let held_norm: BTreeSet<String> = held.iter().map(|k| normalize_key_name(k)).collect();
    let mut out = Vec::new();
    for item in arr {
        let Some(name) = item.get("name").and_then(Value::as_str) else {
            continue;
        };
        if name.is_empty() {
            continue;
        }
        let typ = item.get("type").and_then(Value::as_str).unwrap_or("button");
        let mut value = 0.0f32;
        if let Some(keys) = item.get("keys").and_then(Value::as_array) {
            for key in keys {
                match key {
                    Value::String(k) if held_norm.contains(&normalize_key_name(k)) => {
                        value = 1.0;
                    }
                    Value::Array(pair) if pair.len() >= 2 => {
                        if let (Some(k), Some(weight)) = (pair[0].as_str(), pair[1].as_f64()) {
                            if held_norm.contains(&normalize_key_name(k)) {
                                value += weight as f32;
                            }
                        }
                    }
                    _ => {}
                }
            }
        }
        if typ == "axis" {
            value = value.clamp(-1.0, 1.0);
        } else if value > 0.0 {
            value = 1.0;
        }
        for frame_offset in 0..HOLD_FRAMES {
            out.push(json!({
                "action": name,
                "value": value,
                "frame_offset": frame_offset
            }));
        }
    }
    out
}

pub fn held_from_egui(ctx: &egui::Context) -> BTreeSet<String> {
    const KEYS: &[(egui::Key, &str)] = &[
        (egui::Key::A, "A"),
        (egui::Key::B, "B"),
        (egui::Key::C, "C"),
        (egui::Key::D, "D"),
        (egui::Key::E, "E"),
        (egui::Key::F, "F"),
        (egui::Key::G, "G"),
        (egui::Key::H, "H"),
        (egui::Key::I, "I"),
        (egui::Key::J, "J"),
        (egui::Key::K, "K"),
        (egui::Key::L, "L"),
        (egui::Key::M, "M"),
        (egui::Key::N, "N"),
        (egui::Key::O, "O"),
        (egui::Key::P, "P"),
        (egui::Key::Q, "Q"),
        (egui::Key::R, "R"),
        (egui::Key::S, "S"),
        (egui::Key::T, "T"),
        (egui::Key::U, "U"),
        (egui::Key::V, "V"),
        (egui::Key::W, "W"),
        (egui::Key::X, "X"),
        (egui::Key::Y, "Y"),
        (egui::Key::Z, "Z"),
        (egui::Key::Num0, "0"),
        (egui::Key::Num1, "1"),
        (egui::Key::Num2, "2"),
        (egui::Key::Num3, "3"),
        (egui::Key::Num4, "4"),
        (egui::Key::Num5, "5"),
        (egui::Key::Num6, "6"),
        (egui::Key::Num7, "7"),
        (egui::Key::Num8, "8"),
        (egui::Key::Num9, "9"),
        (egui::Key::Space, "Space"),
        (egui::Key::ArrowLeft, "Left"),
        (egui::Key::ArrowRight, "Right"),
        (egui::Key::ArrowUp, "Up"),
        (egui::Key::ArrowDown, "Down"),
        (egui::Key::Enter, "Enter"),
        (egui::Key::Escape, "Escape"),
        (egui::Key::Comma, "Comma"),
        (egui::Key::Period, "Period"),
    ];
    let mut held = BTreeSet::new();
    ctx.input(|i| {
        for (key, name) in KEYS {
            if i.key_down(*key) {
                held.insert((*name).to_string());
            }
        }
    });
    held
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn held_d_sets_move_x() {
        let map = json!({
            "actions": [
                {
                    "name": "move_x",
                    "type": "axis",
                    "keys": [["A", -1.0], ["D", 1.0]]
                },
                { "name": "jump", "type": "button", "keys": ["Space"] }
            ]
        });
        let mut held = BTreeSet::new();
        held.insert("D".into());
        let actions = actions_from_held(&map, &held);
        assert_eq!(actions.len(), 2 * HOLD_FRAMES as usize);
        assert_eq!(actions[0]["action"], "move_x");
        assert_eq!(actions[0]["value"], 1.0);
        assert_eq!(actions[0]["frame_offset"], 0);
        assert_eq!(actions[7]["frame_offset"], 7);
        assert_eq!(actions[8]["action"], "jump");
        assert_eq!(actions[8]["value"], 0.0);
    }
}
