use serde_json::{Map, Value};

/// Canonical JSON bytes (MASTER 5.4b, spike subset).
///
/// - object keys sorted bytewise UTF-8, recursively
/// - 2-space indent, LF, UTF-8 no BOM
/// - trailing newline
/// - floats: serde_json / ryu-equivalent shortest form as emitted by
///   `serde_json::Number`; `-0.0` is normalized to `0.0` before write
pub fn canonical_bytes(value: &Value) -> Vec<u8> {
    let normalized = normalize_value(value);
    let mut text = serde_json::to_string_pretty(&normalized)
        .expect("canonical JSON serialization is infallible for Value");
    text = text.replace("\r\n", "\n");
    if !text.ends_with('\n') {
        text.push('\n');
    }
    text.into_bytes()
}

pub fn parse_json_bytes(bytes: &[u8]) -> Result<Value, serde_json::Error> {
    serde_json::from_slice(bytes)
}

fn normalize_value(value: &Value) -> Value {
    match value {
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort_by(|a, b| a.as_str().cmp(b.as_str()));
            let mut out = Map::new();
            for key in keys {
                out.insert(key.clone(), normalize_value(&map[key]));
            }
            Value::Object(out)
        }
        Value::Array(items) => Value::Array(items.iter().map(normalize_value).collect()),
        Value::Number(n) => normalize_number(n),
        other => other.clone(),
    }
}

fn normalize_number(n: &serde_json::Number) -> Value {
    if let Some(f) = n.as_f64() {
        // MASTER 5.4b: -0.0 -> 0.0 before write.
        if f.to_bits() == (-0.0f64).to_bits() {
            return Value::from(0.0);
        }
    }
    Value::Number(n.clone())
}
