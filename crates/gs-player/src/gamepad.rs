//! Snapshot `input-map.json` gamepad fields (MASTER 6.4). Window path only.

use std::collections::BTreeMap;

use gs_runtime_core::InputFrame;
use serde_json::Value;

/// Last-seen abstract pad state (names from the input map, not gilrs types).
#[derive(Clone, Debug, Default, PartialEq)]
pub(crate) struct GamepadSample {
    pub buttons: BTreeMap<String, bool>,
    pub axes: BTreeMap<String, f32>,
}

impl GamepadSample {
    pub(crate) fn clear(&mut self) {
        self.buttons.clear();
        self.axes.clear();
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct GamepadBinding {
    pub action: String,
    pub button: Option<String>,
    pub axis: Option<String>,
}

pub(crate) fn bindings_from_input_map(value: &Value) -> Vec<GamepadBinding> {
    let Some(arr) = value.get("actions").and_then(Value::as_array) else {
        return Vec::new();
    };
    let mut out = Vec::new();
    for item in arr {
        let Some(name) = item.get("name").and_then(Value::as_str) else {
            continue;
        };
        if name.is_empty() {
            continue;
        }
        let button = item
            .get("gamepad_button")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
            .map(str::to_string);
        let axis = item
            .get("gamepad_axis")
            .and_then(Value::as_str)
            .filter(|s| !s.is_empty())
            .map(str::to_string);
        if button.is_none() && axis.is_none() {
            continue;
        }
        out.push(GamepadBinding {
            action: name.to_string(),
            button,
            axis,
        });
    }
    out
}

pub(crate) fn apply_gamepad_sample(
    frame: &mut InputFrame,
    bindings: &[GamepadBinding],
    sample: &GamepadSample,
) {
    for binding in bindings {
        if let Some(button) = &binding.button {
            if sample.buttons.get(button) == Some(&true) {
                frame.actions.insert(binding.action.clone(), 1.0);
            }
        }
        if let Some(axis) = &binding.axis {
            if let Some(value) = sample.axes.get(axis) {
                let v = if value.is_finite() {
                    value.clamp(-1.0, 1.0)
                } else {
                    0.0
                };
                frame.actions.insert(binding.action.clone(), v);
            }
        }
    }
}

pub(crate) fn button_name(button: gilrs::Button) -> Option<&'static str> {
    use gilrs::Button;
    Some(match button {
        Button::South => "south",
        Button::East => "east",
        Button::North => "north",
        Button::West => "west",
        Button::C => "c",
        Button::Z => "z",
        Button::LeftTrigger => "left_trigger",
        Button::LeftTrigger2 => "left_trigger2",
        Button::RightTrigger => "right_trigger",
        Button::RightTrigger2 => "right_trigger2",
        Button::Select => "select",
        Button::Start => "start",
        Button::Mode => "mode",
        Button::LeftThumb => "left_thumb",
        Button::RightThumb => "right_thumb",
        Button::DPadUp => "dpad_up",
        Button::DPadDown => "dpad_down",
        Button::DPadLeft => "dpad_left",
        Button::DPadRight => "dpad_right",
        Button::Unknown => return None,
    })
}

pub(crate) fn axis_name(axis: gilrs::Axis) -> Option<&'static str> {
    use gilrs::Axis;
    Some(match axis {
        Axis::LeftStickX => "left_x",
        Axis::LeftStickY => "left_y",
        Axis::LeftZ => "left_z",
        Axis::RightStickX => "right_x",
        Axis::RightStickY => "right_y",
        Axis::RightZ => "right_z",
        Axis::DPadX => "dpad_x",
        Axis::DPadY => "dpad_y",
        Axis::Unknown => return None,
    })
}

/// Poll gilrs. Missing/unplugged devices must not abort (GS-EC-33).
pub(crate) fn try_open_gilrs() -> Option<gilrs::Gilrs> {
    gilrs::Gilrs::new().ok()
}

pub(crate) fn poll_gilrs(gilrs: &mut gilrs::Gilrs, sample: &mut GamepadSample) {
    while let Some(event) = gilrs.next_event() {
        match event.event {
            gilrs::EventType::ButtonPressed(button, _) => {
                if let Some(name) = button_name(button) {
                    sample.buttons.insert(name.to_string(), true);
                }
            }
            gilrs::EventType::ButtonReleased(button, _) => {
                if let Some(name) = button_name(button) {
                    sample.buttons.insert(name.to_string(), false);
                }
            }
            gilrs::EventType::AxisChanged(axis, value, _) => {
                if let Some(name) = axis_name(axis) {
                    let v = if value.is_finite() {
                        value.clamp(-1.0, 1.0)
                    } else {
                        0.0
                    };
                    sample.axes.insert(name.to_string(), v);
                }
            }
            gilrs::EventType::Disconnected => sample.clear(),
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::input::input_frame_from_map;
    use serde_json::json;

    #[test]
    fn south_button_maps_to_interact() {
        let map = json!({
            "actions": [
                {
                    "name": "move_x",
                    "type": "axis",
                    "keys": [["A", -1.0], ["D", 1.0]],
                    "gamepad_axis": "left_x"
                },
                {
                    "name": "interact",
                    "type": "button",
                    "keys": ["E"],
                    "gamepad_button": "south"
                }
            ]
        });
        let bindings = bindings_from_input_map(&map);
        let mut frame = input_frame_from_map(&map);
        assert_eq!(frame.actions.get("interact"), Some(&0.0));

        let mut sample = GamepadSample::default();
        sample.buttons.insert("south".into(), true);
        apply_gamepad_sample(&mut frame, &bindings, &sample);
        assert_eq!(frame.actions.get("interact"), Some(&1.0));
        assert_eq!(frame.actions.get("move_x"), Some(&0.0));

        sample.buttons.insert("south".into(), false);
        sample.axes.insert("left_x".into(), -0.5);
        let mut frame = input_frame_from_map(&map);
        apply_gamepad_sample(&mut frame, &bindings, &sample);
        assert_eq!(frame.actions.get("interact"), Some(&0.0));
        assert_eq!(frame.actions.get("move_x"), Some(&-0.5));
    }

    #[test]
    fn south_name_matches_gilrs_button() {
        assert_eq!(button_name(gilrs::Button::South), Some("south"));
        assert_eq!(axis_name(gilrs::Axis::LeftStickX), Some("left_x"));
    }
}
