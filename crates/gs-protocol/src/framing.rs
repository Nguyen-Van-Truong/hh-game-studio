//! NDJSON framing: one UTF-8 JSON object per line, terminated by LF (MASTER 4.1).

use std::io::{BufRead, Read, Write};

use serde::Serialize;
use serde_json::Value;

use crate::envelope::Message;
use crate::error::ProtocolError;
use crate::MAX_LINE_BYTES;

/// Encode `msg` as one NDJSON line (compact UTF-8 JSON + `'\n'`).
pub fn encode_message<T: Serialize>(msg: &T) -> Result<Vec<u8>, ProtocolError> {
    let mut bytes = serde_json::to_vec(msg).map_err(|err| {
        ProtocolError::invalid_request(format!("failed to encode JSON-RPC message: {err}"))
    })?;
    if bytes.len() > MAX_LINE_BYTES {
        return Err(ProtocolError::proto("NDJSON line exceeds MAX_LINE_BYTES"));
    }
    bytes.push(b'\n');
    Ok(bytes)
}

/// Decode one NDJSON line (trailing LF optional) into a [`Message`].
///
/// Top-level JSON arrays are rejected with [`crate::INVALID_REQUEST`].
/// A line longer than [`MAX_LINE_BYTES`] is [`ProtocolError::proto`].
pub fn decode_message(bytes: &[u8]) -> Result<Message, ProtocolError> {
    let bytes = match bytes.strip_suffix(b"\n") {
        Some(stripped) => stripped,
        None => bytes,
    };
    if bytes.len() > MAX_LINE_BYTES {
        return Err(ProtocolError::proto("NDJSON line exceeds MAX_LINE_BYTES"));
    }
    let value: Value =
        serde_json::from_slice(bytes).map_err(|err| ProtocolError::parse(err.to_string()))?;
    Message::from_value(value)
}

/// Read one NDJSON line from `reader`, enforcing [`MAX_LINE_BYTES`].
///
/// The returned buffer does **not** include the terminating LF.
/// Over-cap or EOF mid-line → [`ProtocolError::proto`] (`E_PROTO` / `-32600`);
/// the caller must close the connection.
pub fn read_ndjson_line<R: BufRead>(reader: &mut R) -> Result<Vec<u8>, ProtocolError> {
    let mut buf = Vec::new();
    let n = reader
        .take(MAX_LINE_BYTES as u64 + 1)
        .read_until(b'\n', &mut buf)?;
    if n == 0 {
        return Err(ProtocolError::Eof);
    }
    if !buf.ends_with(b"\n") {
        return Err(ProtocolError::proto(if buf.len() > MAX_LINE_BYTES {
            "NDJSON line exceeds MAX_LINE_BYTES"
        } else {
            "incomplete NDJSON line (missing LF)"
        }));
    }
    buf.pop();
    if buf.len() > MAX_LINE_BYTES {
        return Err(ProtocolError::proto("NDJSON line exceeds MAX_LINE_BYTES"));
    }
    Ok(buf)
}

/// Write one encoded NDJSON message to `writer`.
pub fn write_ndjson_line<W: Write>(
    writer: &mut W,
    msg: &impl Serialize,
) -> Result<(), ProtocolError> {
    let bytes = encode_message(msg)?;
    writer.write_all(&bytes)?;
    Ok(())
}
