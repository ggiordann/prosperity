use anyhow::Result;
use indexmap::IndexMap;
use serde_json::{Map, Number, Value};

pub fn json_i64(value: i64) -> Value {
    Value::Number(Number::from(value))
}

pub fn json_usize(value: usize) -> Value {
    json_i64(value as i64)
}

pub fn json_f64(value: f64) -> Result<Value> {
    Ok(Value::Number(Number::from_f64(value).ok_or_else(|| {
        anyhow::anyhow!("cannot encode non-finite float")
    })?))
}

pub fn object(entries: Vec<(impl Into<String>, Value)>) -> Value {
    let mut out = Map::new();
    for (key, value) in entries {
        out.insert(key.into(), value);
    }
    Value::Object(out)
}

pub fn index_object(entries: &IndexMap<String, Value>) -> Value {
    let mut out = Map::new();
    for (key, value) in entries {
        out.insert(key.clone(), value.clone());
    }
    Value::Object(out)
}

pub fn sorted_json_bytes(value: &Value) -> Result<Vec<u8>> {
    let mut bytes = serde_json::to_vec_pretty(&sort_value(value))?;
    bytes.push(b'\n');
    Ok(bytes)
}

pub fn pretty_json_bytes(value: &Value) -> Result<Vec<u8>> {
    let mut bytes = serde_json::to_vec_pretty(value)?;
    bytes.push(b'\n');
    Ok(bytes)
}

fn sort_value(value: &Value) -> Value {
    match value {
        Value::Array(items) => Value::Array(items.iter().map(sort_value).collect()),
        Value::Object(map) => {
            let mut keys: Vec<_> = map.keys().cloned().collect();
            keys.sort();
            let mut out = Map::new();
            for key in keys {
                let item = map.get(&key).expect("sorted key missing");
                out.insert(key, sort_value(item));
            }
            Value::Object(out)
        }
        _ => value.clone(),
    }
}

pub fn python_float_string(value: f64) -> String {
    if value.is_nan() || value.is_infinite() {
        return value.to_string();
    }
    if value == 0.0 {
        return if value.is_sign_negative() {
            "-0.0".to_string()
        } else {
            "0.0".to_string()
        };
    }
    if value.fract() == 0.0 {
        return format!("{value:.1}");
    }
    let mut text = value.to_string();
    if !text.contains('.') && !text.contains('e') && !text.contains('E') {
        text.push_str(".0");
    }
    text
}
