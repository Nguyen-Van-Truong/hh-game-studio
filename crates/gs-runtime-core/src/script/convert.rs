use mlua::{Lua, Result as LuaResult, Table, Value as LuaValue};
use serde_json::{Map, Number, Value as JsonValue};

const MAX_DEPTH: usize = 32;

pub fn json_to_lua(lua: &Lua, value: &JsonValue) -> LuaResult<LuaValue> {
    json_to_lua_depth(lua, value, 0)
}

fn json_to_lua_depth(lua: &Lua, value: &JsonValue, depth: usize) -> LuaResult<LuaValue> {
    if depth > MAX_DEPTH {
        return Ok(LuaValue::Nil);
    }
    match value {
        JsonValue::Null => Ok(LuaValue::Nil),
        JsonValue::Bool(b) => Ok(LuaValue::Boolean(*b)),
        JsonValue::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(LuaValue::Integer(i))
            } else if let Some(u) = n.as_u64() {
                Ok(i64::try_from(u)
                    .map(LuaValue::Integer)
                    .unwrap_or_else(|_| LuaValue::Number(u as f64)))
            } else {
                Ok(LuaValue::Number(n.as_f64().unwrap_or(0.0)))
            }
        }
        JsonValue::String(s) => Ok(LuaValue::String(lua.create_string(s)?)),
        JsonValue::Array(items) => {
            let table = lua.create_table()?;
            for (i, item) in items.iter().enumerate() {
                table.set(i + 1, json_to_lua_depth(lua, item, depth + 1)?)?;
            }
            Ok(LuaValue::Table(table))
        }
        JsonValue::Object(obj) => {
            let table = lua.create_table()?;
            for (k, v) in obj {
                table.set(k.as_str(), json_to_lua_depth(lua, v, depth + 1)?)?;
            }
            Ok(LuaValue::Table(table))
        }
    }
}

pub fn lua_to_json(value: &LuaValue) -> JsonValue {
    lua_to_json_depth(value, 0)
}

fn lua_to_json_depth(value: &LuaValue, depth: usize) -> JsonValue {
    if depth > MAX_DEPTH {
        return JsonValue::Null;
    }
    match value {
        LuaValue::Nil => JsonValue::Null,
        LuaValue::Boolean(b) => JsonValue::Bool(*b),
        LuaValue::Integer(i) => JsonValue::Number(Number::from(*i)),
        LuaValue::Number(n) => Number::from_f64(*n)
            .map(JsonValue::Number)
            .unwrap_or(JsonValue::Null),
        LuaValue::String(s) => match s.to_str() {
            Ok(text) => JsonValue::String(text.to_string()),
            Err(_) => JsonValue::Null,
        },
        LuaValue::Table(table) => table_to_json(table, depth),
        _ => JsonValue::Null,
    }
}

fn table_to_json(table: &Table, depth: usize) -> JsonValue {
    let mut pairs: Vec<(LuaValue, LuaValue)> = Vec::new();
    for pair in table.pairs::<LuaValue, LuaValue>().flatten() {
        pairs.push(pair);
    }

    let mut max_index = 0i64;
    let mut is_array = !pairs.is_empty();
    for (key, _) in &pairs {
        match key {
            LuaValue::Integer(i) if *i >= 1 => {
                max_index = max_index.max(*i);
            }
            _ => {
                is_array = false;
                break;
            }
        }
    }
    if is_array && max_index as usize != pairs.len() {
        is_array = false;
    }

    if is_array {
        let mut slots: Vec<JsonValue> = vec![JsonValue::Null; max_index as usize];
        for (key, value) in pairs {
            if let LuaValue::Integer(i) = key {
                let idx = (i - 1) as usize;
                if idx < slots.len() {
                    slots[idx] = lua_to_json_depth(&value, depth + 1);
                }
            }
        }
        JsonValue::Array(slots)
    } else {
        let mut obj = Map::new();
        for (key, value) in pairs {
            let name = match key {
                LuaValue::String(s) => s.to_str().ok().map(|t| t.to_string()),
                LuaValue::Integer(i) => Some(i.to_string()),
                LuaValue::Number(n) => Some(n.to_string()),
                _ => None,
            };
            if let Some(name) = name {
                obj.insert(name, lua_to_json_depth(&value, depth + 1));
            }
        }
        JsonValue::Object(obj)
    }
}

pub fn json_object_from_map(props: &std::collections::BTreeMap<String, JsonValue>) -> JsonValue {
    JsonValue::Object(props.iter().map(|(k, v)| (k.clone(), v.clone())).collect())
}
