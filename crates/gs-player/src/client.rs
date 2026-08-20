//! TCP client for the player control server. Used by the editor bus (I8).
//!
//! Agents must not use this — they call `play.*` on the editor bus.

use std::io::{BufReader, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use gs_protocol::{
    decode_message, read_ndjson_line, write_ndjson_line, ErrorData, Message, Request, Response,
    RpcError, INVALID_REQUEST, PROTOCOL_VER,
};
use serde_json::{json, Value};

use crate::control::{ExitReport, PlayStatus};
use crate::error::Error;
use crate::player_file::{read_player_file, PlayerFile};

/// One connection after `session.hello` with the player token.
pub struct ControlClient {
    writer: TcpStream,
    reader: BufReader<TcpStream>,
    addr: SocketAddr,
    next_id: AtomicU64,
}

impl std::fmt::Debug for ControlClient {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ControlClient")
            .field("addr", &self.addr)
            .field("token", &"<redacted>")
            .finish()
    }
}

impl ControlClient {
    pub fn connect(addr: SocketAddr, token: &str) -> Result<Self, Error> {
        if !addr.ip().is_loopback() {
            return Err(Error::control("player control client must use 127.0.0.1"));
        }
        let stream = TcpStream::connect_timeout(&addr, Duration::from_secs(2))
            .map_err(|e| Error::control(e.to_string()))?;
        stream
            .set_nonblocking(false)
            .map_err(|e| Error::control(e.to_string()))?;
        stream
            .set_nodelay(true)
            .map_err(|e| Error::control(e.to_string()))?;
        stream
            .set_read_timeout(Some(Duration::from_secs(120)))
            .map_err(|e| Error::control(e.to_string()))?;
        stream
            .set_write_timeout(Some(Duration::from_secs(5)))
            .map_err(|e| Error::control(e.to_string()))?;
        let reader = BufReader::new(
            stream
                .try_clone()
                .map_err(|e| Error::control(e.to_string()))?,
        );
        let mut client = Self {
            writer: stream,
            reader,
            addr,
            next_id: AtomicU64::new(1),
        };
        client.call(
            "session.hello",
            json!({
                "token": token,
                "protocol_ver": PROTOCOL_VER,
            }),
        )?;
        Ok(client)
    }

    pub fn connect_player_file(file: &PlayerFile) -> Result<Self, Error> {
        let addr = SocketAddr::from(([127, 0, 0, 1], file.port));
        Self::connect(addr, file.token())
    }

    pub fn connect_player_json(path: &Path) -> Result<Self, Error> {
        let file = read_player_file(path)?;
        Self::connect_player_file(&file)
    }

    pub fn status(&mut self) -> Result<PlayStatus, Error> {
        let value = self.call("play.status", json!({}))?;
        serde_json::from_value(value).map_err(|e| Error::control(e.to_string()))
    }

    pub fn pause(&mut self) -> Result<PlayStatus, Error> {
        let value = self.call("play.pause", json!({}))?;
        serde_json::from_value(value).map_err(|e| Error::control(e.to_string()))
    }

    pub fn resume(&mut self) -> Result<PlayStatus, Error> {
        let value = self.call("play.resume", json!({}))?;
        serde_json::from_value(value).map_err(|e| Error::control(e.to_string()))
    }

    pub fn step_frames(&mut self, n: u32) -> Result<PlayStatus, Error> {
        let value = self.call("play.step_frames", json!({ "n": n }))?;
        serde_json::from_value(value).map_err(|e| Error::control(e.to_string()))
    }

    pub fn set_timescale(&mut self, timescale: f64) -> Result<PlayStatus, Error> {
        let value = self.call("play.set_timescale", json!({ "timescale": timescale }))?;
        serde_json::from_value(value).map_err(|e| Error::control(e.to_string()))
    }

    /// Start writing `play_dir/input.tape.jsonl` (header first).
    pub fn tape_record(&mut self) -> Result<Value, Error> {
        self.call("tape.record", json!({}))
    }

    /// Play-scoped `input.inject`. Values apply on matching upcoming `step_one`s.
    pub fn input_inject(&mut self, play_id: Option<&str>, actions: Value) -> Result<Value, Error> {
        let mut params = json!({ "actions": actions });
        if let Some(play_id) = play_id {
            params["play_id"] = json!(play_id);
        }
        self.call("input.inject", params)
    }

    pub fn stop(&mut self, force: bool) -> Result<ExitReport, Error> {
        let value = self.call("play.stop", json!({ "force": force }))?;
        serde_json::from_value(value).map_err(|e| Error::control(e.to_string()))
    }

    /// Play-scoped hot reload (`script.reload`). Applied after the current frame.
    pub fn script_reload(
        &mut self,
        play_id: Option<&str>,
        path: Option<&str>,
        source: Option<&str>,
        entity_id: Option<&str>,
    ) -> Result<Value, Error> {
        let mut params = json!({});
        if let Some(play_id) = play_id {
            params["play_id"] = json!(play_id);
        }
        if let Some(path) = path {
            params["path"] = json!(path);
        }
        if let Some(source) = source {
            params["source"] = json!(source);
        }
        if let Some(entity_id) = entity_id {
            params["entity_id"] = json!(entity_id);
        }
        self.call("script.reload", params)
    }

    pub fn events(
        &mut self,
        play_id: &str,
        after_seq: u64,
        name: Option<&str>,
        limit: u32,
    ) -> Result<Value, Error> {
        let mut params = json!({
            "play_id": play_id,
            "after_seq": after_seq,
            "limit": limit,
        });
        if let Some(name) = name {
            params["name"] = json!(name);
        }
        self.call("obs.events", params)
    }

    pub fn world_dump(&mut self, play_id: &str) -> Result<Value, Error> {
        self.call("obs.world_dump", json!({ "play_id": play_id }))
    }

    pub fn logs_tail(&mut self, play_id: &str, n: u32) -> Result<Value, Error> {
        self.call("obs.logs_tail", json!({ "play_id": play_id, "n": n }))
    }

    pub fn perf(&mut self, play_id: &str) -> Result<Value, Error> {
        self.call("obs.perf", json!({ "play_id": play_id }))
    }

    pub fn screenshot(&mut self, play_id: &str, max_size: Option<u32>) -> Result<Value, Error> {
        let mut params = json!({ "play_id": play_id });
        if let Some(max_size) = max_size {
            params["max_size"] = json!(max_size);
        }
        self.call("obs.screenshot", params)
    }

    pub fn call(&mut self, method: &str, params: Value) -> Result<Value, Error> {
        let response = self.call_raw(method, params)?;
        match response.error().cloned() {
            Some(err) => Err(Error::control(format_rpc(&err))),
            None => Ok(response.result().cloned().unwrap_or(Value::Null)),
        }
    }

    fn call_raw(&mut self, method: &str, params: Value) -> Result<Response, Error> {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let request = Request::new(id as i64, method, params);
        write_ndjson_line(&mut self.writer, &request)
            .map_err(|err| Error::control(err.to_string()))?;
        self.writer
            .flush()
            .map_err(|err| Error::control(err.to_string()))?;
        loop {
            let line = read_ndjson_line(&mut self.reader)
                .map_err(|err| Error::control(err.to_string()))?;
            match decode_message(&line).map_err(|err| Error::control(err.to_string()))? {
                Message::Response(response) => return Ok(response),
                Message::Notification(_) => continue,
                Message::Request(_) => {
                    return Err(Error::control("player sent a request"));
                }
            }
        }
    }
}

fn format_rpc(err: &RpcError) -> String {
    match &err.data {
        Some(ErrorData { app_code, .. }) => format!("{app_code}: {}", err.message),
        None => {
            if err.code == INVALID_REQUEST {
                err.message.clone()
            } else {
                format!("{}: {}", err.code, err.message)
            }
        }
    }
}
