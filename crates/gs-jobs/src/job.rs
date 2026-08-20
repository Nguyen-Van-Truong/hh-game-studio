//! Job document types. On-disk JSON uses [`BTreeMap`] so keys stay ordered.
//! Unknown fields round-trip except secret names (I8) which are stripped.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::error::Error;

/// Keys that must never appear in job JSON, logs, or result.json (I8).
const SECRET_KEYS: &[&str] = &[
    "token",
    "api_key",
    "apikey",
    "secret",
    "authorization",
    "password",
    "bus_token",
    "access_token",
];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum JobState {
    Queued,
    Running,
    Succeeded,
    Failed,
    Cancelled,
    TimedOut,
}

impl JobState {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Queued => "queued",
            Self::Running => "running",
            Self::Succeeded => "succeeded",
            Self::Failed => "failed",
            Self::Cancelled => "cancelled",
            Self::TimedOut => "timed_out",
        }
    }

    pub fn is_terminal(self) -> bool {
        matches!(
            self,
            Self::Succeeded | Self::Failed | Self::Cancelled | Self::TimedOut
        )
    }

    pub fn late_result_quarantine(self) -> bool {
        matches!(self, Self::Cancelled | Self::TimedOut)
    }

    pub fn parse(raw: &str) -> Option<Self> {
        match raw {
            "queued" => Some(Self::Queued),
            "running" => Some(Self::Running),
            "succeeded" => Some(Self::Succeeded),
            "failed" => Some(Self::Failed),
            "cancelled" => Some(Self::Cancelled),
            "timed_out" => Some(Self::TimedOut),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ImageSize {
    pub w: u32,
    pub h: u32,
}

impl Default for ImageSize {
    fn default() -> Self {
        Self { w: 512, h: 512 }
    }
}

/// MASTER 8.2 job spec fields.
///
/// `dest_rel_hint` is an ingest hint for a later WP — **not** a write path.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct JobSpec {
    pub kind: String,
    pub prompt: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub negative: Option<String>,
    pub size: ImageSize,
    pub seed: i64,
    pub style_preset: String,
    /// Hint only. Workers must never write this path.
    pub dest_rel_hint: String,
    pub command_id: String,
    pub actor_id: String,
    pub created_at: i64,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub extra: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Lease {
    pub worker_id: String,
    pub heartbeat_at: i64,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct JobResult {
    pub ok: bool,
    pub provider: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ms: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub extra: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Job {
    pub job_id: String,
    pub spec: JobSpec,
    pub state: JobState,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub lease: Option<Lease>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub result: Option<JobResult>,
}

impl JobSpec {
    pub fn from_map(map: &BTreeMap<String, Value>) -> Result<Self, Error> {
        let command_id = map
            .get("command_id")
            .and_then(Value::as_str)
            .ok_or_else(|| Error::invalid("command_id is required"))?
            .to_string();
        let size = map.get("size").map(size_from_value).unwrap_or_default();
        let extra = extra_fields(map, SPEC_KEYS);
        Ok(Self {
            kind: map
                .get("kind")
                .and_then(Value::as_str)
                .unwrap_or("image")
                .to_string(),
            prompt: map
                .get("prompt")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string(),
            negative: map
                .get("negative")
                .and_then(Value::as_str)
                .map(str::to_string),
            size,
            seed: map.get("seed").and_then(Value::as_i64).unwrap_or(0),
            style_preset: map
                .get("style_preset")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string(),
            dest_rel_hint: map
                .get("dest_rel_hint")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string(),
            command_id,
            actor_id: map
                .get("actor_id")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string(),
            created_at: map.get("created_at").and_then(Value::as_i64).unwrap_or(0),
            extra,
        })
    }

    pub fn to_map(&self) -> BTreeMap<String, Value> {
        let mut map = BTreeMap::new();
        map.insert("actor_id".into(), json!(self.actor_id));
        map.insert("command_id".into(), json!(self.command_id));
        map.insert("created_at".into(), json!(self.created_at));
        map.insert("dest_rel_hint".into(), json!(self.dest_rel_hint));
        map.insert("kind".into(), json!(self.kind));
        if let Some(neg) = &self.negative {
            map.insert("negative".into(), json!(neg));
        }
        map.insert("prompt".into(), json!(self.prompt));
        map.insert("seed".into(), json!(self.seed));
        map.insert("size".into(), size_to_value(self.size));
        map.insert("style_preset".into(), json!(self.style_preset));
        for (k, v) in &self.extra {
            if !is_secret_key(k) {
                map.insert(k.clone(), v.clone());
            }
        }
        strip_secrets(&mut map);
        map
    }
}

impl JobResult {
    pub fn from_map(map: &BTreeMap<String, Value>) -> Self {
        Self {
            ok: map.get("ok").and_then(Value::as_bool).unwrap_or(false),
            provider: map
                .get("provider")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string(),
            ms: map.get("ms").and_then(Value::as_u64),
            error: map.get("error").and_then(Value::as_str).map(str::to_string),
            extra: extra_fields(map, RESULT_KEYS),
        }
    }

    pub fn to_map(&self) -> BTreeMap<String, Value> {
        let mut map = BTreeMap::new();
        map.insert("ok".into(), json!(self.ok));
        map.insert("provider".into(), json!(self.provider));
        if let Some(ms) = self.ms {
            map.insert("ms".into(), json!(ms));
        }
        if let Some(err) = &self.error {
            map.insert("error".into(), json!(err));
        }
        for (k, v) in &self.extra {
            if !is_secret_key(k) {
                map.insert(k.clone(), v.clone());
            }
        }
        strip_secrets(&mut map);
        map
    }
}

impl Job {
    pub fn from_map(
        job_id: &str,
        map: &BTreeMap<String, Value>,
        fallback: JobState,
    ) -> Result<Self, Error> {
        let state = map
            .get("state")
            .and_then(Value::as_str)
            .and_then(JobState::parse)
            .unwrap_or(fallback);
        let lease = map.get("lease").and_then(Value::as_object).map(|o| Lease {
            worker_id: o
                .get("worker_id")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string(),
            heartbeat_at: o.get("heartbeat_at").and_then(Value::as_i64).unwrap_or(0),
        });
        let result = map.get("result").and_then(Value::as_object).map(|o| {
            let tree: BTreeMap<String, Value> =
                o.iter().map(|(k, v)| (k.clone(), v.clone())).collect();
            JobResult::from_map(&tree)
        });
        Ok(Self {
            job_id: job_id.to_string(),
            spec: JobSpec::from_map(map)?,
            state,
            lease,
            result,
        })
    }

    pub fn to_map(&self) -> BTreeMap<String, Value> {
        let mut map = self.spec.to_map();
        map.insert("job_id".into(), json!(self.job_id));
        map.insert("state".into(), json!(self.state.as_str()));
        if let Some(lease) = &self.lease {
            let mut lease_map = BTreeMap::new();
            lease_map.insert("heartbeat_at".into(), json!(lease.heartbeat_at));
            lease_map.insert("worker_id".into(), json!(lease.worker_id));
            map.insert(
                "lease".into(),
                Value::Object(lease_map.into_iter().collect()),
            );
        }
        if let Some(result) = &self.result {
            map.insert(
                "result".into(),
                Value::Object(result.to_map().into_iter().collect()),
            );
        }
        strip_secrets(&mut map);
        map
    }
}

const SPEC_KEYS: &[&str] = &[
    "kind",
    "prompt",
    "negative",
    "size",
    "seed",
    "style_preset",
    "dest_rel_hint",
    "command_id",
    "actor_id",
    "created_at",
    "job_id",
    "state",
    "lease",
    "result",
    "late_result",
];

const RESULT_KEYS: &[&str] = &["ok", "provider", "ms", "error"];

pub fn strip_secrets(map: &mut BTreeMap<String, Value>) {
    map.retain(|k, _| !is_secret_key(k));
}

pub fn is_secret_key(key: &str) -> bool {
    SECRET_KEYS.iter().any(|s| key.eq_ignore_ascii_case(s))
}

fn extra_fields(map: &BTreeMap<String, Value>, known: &[&str]) -> BTreeMap<String, Value> {
    map.iter()
        .filter(|(k, _)| !known.contains(&k.as_str()) && !is_secret_key(k))
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect()
}

fn size_from_value(v: &Value) -> ImageSize {
    if let Some(o) = v.as_object() {
        let w = o
            .get("w")
            .or_else(|| o.get("width"))
            .and_then(Value::as_u64)
            .unwrap_or(512) as u32;
        let h = o
            .get("h")
            .or_else(|| o.get("height"))
            .and_then(Value::as_u64)
            .unwrap_or(512) as u32;
        return ImageSize { w, h };
    }
    if let Some(s) = v.as_str() {
        if let Some((w, h)) = s.split_once('x') {
            if let (Ok(w), Ok(h)) = (w.parse(), h.parse()) {
                return ImageSize { w, h };
            }
        }
    }
    ImageSize::default()
}

fn size_to_value(size: ImageSize) -> Value {
    let mut m = BTreeMap::new();
    m.insert("h".into(), json!(size.h));
    m.insert("w".into(), json!(size.w));
    Value::Object(m.into_iter().collect())
}
