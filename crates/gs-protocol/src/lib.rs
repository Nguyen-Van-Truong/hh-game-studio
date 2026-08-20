//! JSON-RPC 2.0 envelope + NDJSON framing (MASTER 4.1).

mod envelope;
mod error;
mod framing;

pub use envelope::{Id, JsonRpcVersion, Message, Notification, Request, Response, ResponsePayload};
pub use error::{
    ErrorData, ProtocolError, RpcError, APP, APP_CODE_PROTO, BUSY, CONFLICT, INVALID_PARAMS,
    INVALID_REQUEST, METHOD_NOT_FOUND, PARSE, UNAUTHORIZED,
};
pub use framing::{decode_message, encode_message, read_ndjson_line, write_ndjson_line};

pub const PROTOCOL_VER: &str = "1.0";
pub const JSONRPC_VERSION: &str = "2.0";
pub const MAX_LINE_BYTES: usize = 4 * 1024 * 1024;
pub const SLOWLORIS_SECS: u64 = 10;
pub const IDLE_TIMEOUT_SECS: u64 = 120;

pub fn protocol_ver() -> &'static str {
    PROTOCOL_VER
}

#[cfg(test)]
mod tests {
    use std::io::Cursor;

    use serde_json::{json, Value};

    use super::*;

    fn assert_round_trip<T>(value: &T)
    where
        T: serde::Serialize + serde::de::DeserializeOwned + PartialEq + std::fmt::Debug,
    {
        let encoded = serde_json::to_value(value).expect("serialize");
        let decoded: T = serde_json::from_value(encoded).expect("deserialize");
        assert_eq!(*value, decoded);
    }

    #[test]
    fn smoke_protocol_ver() {
        assert_eq!(protocol_ver(), "1.0");
        assert_eq!(PROTOCOL_VER, "1.0");
        assert_eq!(JSONRPC_VERSION, "2.0");
        assert_eq!(MAX_LINE_BYTES, 4 * 1024 * 1024);
        assert_eq!(SLOWLORIS_SECS, 10);
        assert_eq!(IDLE_TIMEOUT_SECS, 120);
    }

    #[test]
    fn request_response_event_serde_round_trip() {
        let request = Request::new(
            "a-000123",
            "entity.spawn",
            json!({
                "scene_id": "s_main",
                "command_id": "01J...ULID",
            }),
        );
        assert_round_trip(&request);
        let request_line = encode_message(&request).expect("encode request");
        assert_eq!(
            decode_message(&request_line).expect("decode request"),
            Message::Request(request.clone())
        );

        let ok = Response::ok(
            "a-000123",
            json!({
                "revision": "r-000451",
                "txn_id": "t-000318",
            }),
        );
        assert_round_trip(&ok);
        let ok_line = encode_message(&ok).expect("encode ok");
        assert_eq!(
            decode_message(&ok_line).expect("decode ok"),
            Message::Response(ok)
        );

        let err = Response::err(
            "a-000123",
            RpcError::with_data(
                INVALID_PARAMS,
                "invalid params",
                ErrorData {
                    app_code: "E_VALIDATION".to_owned(),
                    retryable: Some(false),
                    field: Some("x".to_owned()),
                    reason: Some("nan".to_owned()),
                },
            ),
        );
        assert_round_trip(&err);
        let err_line = encode_message(&err).expect("encode err");
        assert_eq!(
            decode_message(&err_line).expect("decode err"),
            Message::Response(err)
        );

        let event = Notification::new(
            "event.scene_changed",
            json!({
                "seq": 4512,
                "actor_id": "act_02",
                "txn_id": "t-000318",
                "summary": "entity.spawn crate_1",
                "entities": ["e_000042"],
                "revision": "r-000451",
            }),
        );
        assert_round_trip(&event);
        let event_line = encode_message(&event).expect("encode event");
        assert_eq!(
            decode_message(&event_line).expect("decode event"),
            Message::Notification(event)
        );
    }

    #[test]
    fn error_code_serializes_as_number() {
        let error = RpcError::new(INVALID_PARAMS, "invalid params");
        let value = serde_json::to_value(&error).expect("serialize error");
        assert!(
            value["code"].is_number(),
            "error.code must be a JSON number"
        );
        assert!(!value["code"].is_string());
        assert_eq!(value["code"], json!(-32602));

        let response = Response::err("a-000123", error);
        let raw = serde_json::to_string(&response).expect("serialize response");
        assert!(
            raw.contains("\"code\":-32602"),
            "wire JSON must contain numeric code, got {raw}"
        );
        assert!(
            !raw.contains("\"code\":\"-32602\""),
            "error.code must never be a string"
        );
    }

    #[test]
    fn line_over_4mb_is_proto_error() {
        let mut oversized = vec![b'x'; MAX_LINE_BYTES + 1];
        oversized.push(b'\n');
        let mut cursor = Cursor::new(oversized);
        let err = read_ndjson_line(&mut cursor).expect_err("over-cap line");
        assert_eq!(err.code(), Some(INVALID_REQUEST));
        assert_eq!(err.app_code(), Some(APP_CODE_PROTO));

        let huge = vec![b'{'; MAX_LINE_BYTES + 1];
        let err = decode_message(&huge).expect_err("over-cap decode");
        assert_eq!(err.code(), Some(INVALID_REQUEST));
        assert_eq!(err.app_code(), Some(APP_CODE_PROTO));
    }

    #[test]
    fn json_array_batch_is_invalid_request() {
        let batch = b"[{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"session.ping\"}]\n";
        let err = decode_message(batch).expect_err("batch");
        assert_eq!(err.code(), Some(INVALID_REQUEST));
        assert_eq!(err.code(), Some(-32600));
    }

    #[test]
    fn notification_has_no_id() {
        let event = Notification::new("event.scene_changed", json!({"seq": 1}));
        let value = serde_json::to_value(&event).expect("serialize notification");
        assert!(
            value.get("id").is_none(),
            "notification must omit id, got {value}"
        );

        let line = encode_message(&event).expect("encode notification");
        let parsed: Value = serde_json::from_slice(&line[..line.len() - 1]).expect("json");
        assert!(parsed.get("id").is_none());
        assert_eq!(parsed["jsonrpc"], "2.0");
        assert_eq!(parsed["method"], "event.scene_changed");

        match decode_message(&line).expect("decode notification") {
            Message::Notification(decoded) => assert_eq!(decoded, event),
            other => panic!("expected notification, got {other:?}"),
        }
    }

    #[test]
    fn number_and_string_ids_round_trip() {
        let string_id = Request::new("a-000123", "session.ping", json!({}));
        let number_id = Request::new(7_i64, "session.ping", Value::Null);
        assert_round_trip(&string_id);
        assert_round_trip(&number_id);

        let wire = serde_json::to_value(&number_id).expect("serialize");
        assert!(wire["id"].is_number());
        assert_eq!(wire["id"], json!(7));
    }

    #[test]
    fn write_then_read_ndjson_line() {
        let request = Request::new("n-1", "session.hello", json!({"protocol_ver": "1.0"}));
        let mut buf = Vec::new();
        write_ndjson_line(&mut buf, &request).expect("write");
        assert_eq!(*buf.last().expect("lf"), b'\n');

        let mut cursor = Cursor::new(buf);
        let line = read_ndjson_line(&mut cursor).expect("read");
        assert_eq!(
            decode_message(&line).expect("decode"),
            Message::Request(request)
        );
        assert!(matches!(
            read_ndjson_line(&mut cursor).expect_err("eof"),
            ProtocolError::Eof
        ));
    }
}
