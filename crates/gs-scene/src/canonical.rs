//! Canonical JSON writer (MASTER 5.4b).
//!
//! Recursive UTF-8 key sort, entities sorted by numeric id, `-0.0` → `0.0`,
//! shortest-round-trip floats via ryu, 2-space indent, LF, trailing newline.

use serde_json::{Map, Value};

pub fn to_canonical_string(value: &Value) -> String {
    let mut out = String::new();
    write_value(&mut out, value, 0);
    out.push('\n');
    out
}

pub fn to_canonical_vec(value: &Value) -> Vec<u8> {
    to_canonical_string(value).into_bytes()
}

fn write_value(out: &mut String, value: &Value, indent: usize) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(n) => out.push_str(&format_number(n)),
        Value::String(s) => write_string(out, s),
        Value::Array(items) => write_array(out, items, indent),
        Value::Object(map) => write_object(out, map, indent),
    }
}

fn format_number(n: &serde_json::Number) -> String {
    if let Some(i) = n.as_i64() {
        return i.to_string();
    }
    if let Some(u) = n.as_u64() {
        return u.to_string();
    }
    let Some(mut f) = n.as_f64() else {
        return n.to_string();
    };
    if f == 0.0 {
        f = 0.0;
    }
    let mut buf = ryu::Buffer::new();
    buf.format_finite(f).to_string()
}

fn write_string(out: &mut String, s: &str) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

fn write_array(out: &mut String, items: &[Value], indent: usize) {
    if items.is_empty() {
        out.push_str("[]");
        return;
    }
    out.push_str("[\n");
    for (i, item) in items.iter().enumerate() {
        write_indent(out, indent + 1);
        write_value(out, item, indent + 1);
        if i + 1 != items.len() {
            out.push(',');
        }
        out.push('\n');
    }
    write_indent(out, indent);
    out.push(']');
}

fn write_object(out: &mut String, map: &Map<String, Value>, indent: usize) {
    if map.is_empty() {
        out.push_str("{}");
        return;
    }
    let mut keys: Vec<&String> = map.keys().collect();
    keys.sort_by(|a, b| a.as_str().cmp(b.as_str()));
    out.push_str("{\n");
    for (i, key) in keys.iter().enumerate() {
        write_indent(out, indent + 1);
        write_string(out, key);
        out.push_str(": ");
        write_value(out, &map[*key], indent + 1);
        if i + 1 != keys.len() {
            out.push(',');
        }
        out.push('\n');
    }
    write_indent(out, indent);
    out.push('}');
}

fn write_indent(out: &mut String, indent: usize) {
    for _ in 0..indent {
        out.push_str("  ");
    }
}

pub fn json_f64(v: f64) -> Value {
    let v = if v == 0.0 { 0.0 } else { v };
    serde_json::Number::from_f64(v)
        .map(Value::Number)
        .unwrap_or(Value::Null)
}

pub fn json_f32(v: f32) -> Value {
    json_f64(f64::from(v))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn sorts_keys_and_normalizes_neg_zero() {
        let mut map = Map::new();
        map.insert("z".into(), json!(1));
        map.insert("a".into(), json_f64(-0.0));
        let s = to_canonical_string(&Value::Object(map));
        assert_eq!(s, "{\n  \"a\": 0.0,\n  \"z\": 1\n}\n");
    }
}
