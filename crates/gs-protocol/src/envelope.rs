//! JSON-RPC 2.0 envelope types (MASTER 4.1).

use std::borrow::Cow;
use std::fmt;

use serde::de::{self, Deserializer};
use serde::ser::Serializer;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::error::{ProtocolError, RpcError};
use crate::JSONRPC_VERSION;

/// Wire `jsonrpc` field; always the string `"2.0"`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct JsonRpcVersion;

impl JsonRpcVersion {
    pub const V2: Self = Self;
}

impl Serialize for JsonRpcVersion {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.serialize_str(JSONRPC_VERSION)
    }
}

impl<'de> Deserialize<'de> for JsonRpcVersion {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let raw = Cow::<str>::deserialize(deserializer)?;
        if raw == JSONRPC_VERSION {
            Ok(Self)
        } else {
            Err(de::Error::custom("jsonrpc must be \"2.0\""))
        }
    }
}

/// Request / response `id`: JSON string or number (never null).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Id {
    String(String),
    Number(serde_json::Number),
}

impl From<String> for Id {
    fn from(value: String) -> Self {
        Self::String(value)
    }
}

impl From<&str> for Id {
    fn from(value: &str) -> Self {
        Self::String(value.to_owned())
    }
}

impl From<i64> for Id {
    fn from(value: i64) -> Self {
        Self::Number(value.into())
    }
}

impl From<u64> for Id {
    fn from(value: u64) -> Self {
        Self::Number(value.into())
    }
}

impl From<i32> for Id {
    fn from(value: i32) -> Self {
        Self::from(i64::from(value))
    }
}

impl fmt::Display for Id {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::String(s) => f.write_str(s),
            Self::Number(n) => write!(f, "{n}"),
        }
    }
}

/// JSON-RPC request (`id` + `method`).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Request {
    pub jsonrpc: JsonRpcVersion,
    pub id: Id,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

impl Request {
    pub fn new(id: impl Into<Id>, method: impl Into<String>, params: Value) -> Self {
        Self {
            jsonrpc: JsonRpcVersion,
            id: id.into(),
            method: method.into(),
            params,
        }
    }
}

/// Success vs error body of a response (`result` XOR `error`).
#[derive(Debug, Clone, PartialEq)]
pub enum ResponsePayload {
    Result(Value),
    Error(RpcError),
}

/// JSON-RPC response.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(try_from = "RawResponse", into = "RawResponse")]
pub struct Response {
    pub jsonrpc: JsonRpcVersion,
    pub id: Id,
    pub payload: ResponsePayload,
}

impl Response {
    pub fn ok(id: impl Into<Id>, result: Value) -> Self {
        Self {
            jsonrpc: JsonRpcVersion,
            id: id.into(),
            payload: ResponsePayload::Result(result),
        }
    }

    pub fn err(id: impl Into<Id>, error: RpcError) -> Self {
        Self {
            jsonrpc: JsonRpcVersion,
            id: id.into(),
            payload: ResponsePayload::Error(error),
        }
    }

    pub fn result(&self) -> Option<&Value> {
        match &self.payload {
            ResponsePayload::Result(value) => Some(value),
            ResponsePayload::Error(_) => None,
        }
    }

    pub fn error(&self) -> Option<&RpcError> {
        match &self.payload {
            ResponsePayload::Error(error) => Some(error),
            ResponsePayload::Result(_) => None,
        }
    }
}

#[derive(Serialize, Deserialize)]
struct RawResponse {
    jsonrpc: JsonRpcVersion,
    id: Id,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    result: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    error: Option<RpcError>,
}

impl From<Response> for RawResponse {
    fn from(response: Response) -> Self {
        match response.payload {
            ResponsePayload::Result(result) => Self {
                jsonrpc: response.jsonrpc,
                id: response.id,
                result: Some(result),
                error: None,
            },
            ResponsePayload::Error(error) => Self {
                jsonrpc: response.jsonrpc,
                id: response.id,
                result: None,
                error: Some(error),
            },
        }
    }
}

impl TryFrom<RawResponse> for Response {
    type Error = &'static str;

    fn try_from(raw: RawResponse) -> Result<Self, Self::Error> {
        match (raw.result, raw.error) {
            (Some(result), None) => Ok(Self {
                jsonrpc: raw.jsonrpc,
                id: raw.id,
                payload: ResponsePayload::Result(result),
            }),
            (None, Some(error)) => Ok(Self {
                jsonrpc: raw.jsonrpc,
                id: raw.id,
                payload: ResponsePayload::Error(error),
            }),
            (Some(_), Some(_)) => Err("JSON-RPC response must not contain both result and error"),
            (None, None) => Err("JSON-RPC response must contain result or error"),
        }
    }
}

/// JSON-RPC notification / event. Wire form has **no** `id`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Notification {
    pub jsonrpc: JsonRpcVersion,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

impl Notification {
    pub fn new(method: impl Into<String>, params: Value) -> Self {
        Self {
            jsonrpc: JsonRpcVersion,
            method: method.into(),
            params,
        }
    }
}

/// One decoded NDJSON message.
#[derive(Debug, Clone, PartialEq)]
pub enum Message {
    Request(Request),
    Response(Response),
    Notification(Notification),
}

impl Message {
    pub fn from_value(value: Value) -> Result<Self, ProtocolError> {
        if value.is_array() {
            return Err(ProtocolError::invalid_request(
                "JSON-RPC batch arrays are not supported",
            ));
        }
        let obj = value.as_object().ok_or_else(|| {
            ProtocolError::invalid_request("JSON-RPC message must be a JSON object")
        })?;

        match obj.get("jsonrpc").and_then(Value::as_str) {
            Some(JSONRPC_VERSION) => {}
            _ => {
                return Err(ProtocolError::invalid_request("jsonrpc must be \"2.0\""));
            }
        }

        if obj.contains_key("method") {
            if obj.contains_key("id") {
                let request = serde_json::from_value(value)
                    .map_err(|err| ProtocolError::invalid_request(err.to_string()))?;
                Ok(Self::Request(request))
            } else {
                let notification = serde_json::from_value(value)
                    .map_err(|err| ProtocolError::invalid_request(err.to_string()))?;
                Ok(Self::Notification(notification))
            }
        } else if obj.contains_key("result") || obj.contains_key("error") {
            let response = serde_json::from_value(value)
                .map_err(|err| ProtocolError::invalid_request(err.to_string()))?;
            Ok(Self::Response(response))
        } else {
            Err(ProtocolError::invalid_request(
                "JSON-RPC message must be a request, response, or notification",
            ))
        }
    }
}

impl Serialize for Message {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        match self {
            Self::Request(msg) => msg.serialize(serializer),
            Self::Response(msg) => msg.serialize(serializer),
            Self::Notification(msg) => msg.serialize(serializer),
        }
    }
}

impl<'de> Deserialize<'de> for Message {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let value = Value::deserialize(deserializer)?;
        Self::from_value(value).map_err(de::Error::custom)
    }
}
