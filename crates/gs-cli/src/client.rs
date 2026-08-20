//! Thin TCP bus client: endpoint → hello → JSON-RPC calls. No document logic.

use std::io::{BufReader, Write};
use std::net::{Shutdown, SocketAddr, TcpStream};
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use gs_protocol::{
    decode_message, read_ndjson_line, write_ndjson_line, Message, Notification, Request, Response,
    RpcError, PROTOCOL_VER,
};
use serde_json::{json, Value};

use crate::command_id::ensure_command_id;
use crate::endpoint::{self, Endpoint};
use crate::error::Error;

const CONNECT_TIMEOUT: Duration = Duration::from_secs(2);
const IO_TIMEOUT: Duration = Duration::from_secs(10);
const DEFAULT_CLIENT_NAME: &str = "gs.ps1";

/// Result of `session.hello`.
#[derive(Debug, Clone)]
pub struct HelloInfo {
    pub actor_id: String,
    pub principal: String,
    pub protocol_ver: String,
    pub result: Value,
}

/// A call that may have auto-inserted `command_id`.
#[derive(Debug, Clone)]
pub struct InvokeResult {
    pub command_id: Option<String>,
    pub result: Value,
}

/// One TCP agent connection after a successful `session.hello`.
pub struct BusClient {
    writer: TcpStream,
    reader: BufReader<TcpStream>,
    endpoint: Endpoint,
    hello: HelloInfo,
    next_id: AtomicU64,
}

impl std::fmt::Debug for BusClient {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("BusClient")
            .field("endpoint", &self.endpoint)
            .field("actor_id", &self.hello.actor_id)
            .field("principal", &self.hello.principal)
            .finish()
    }
}

impl BusClient {
    /// Read a live endpoint at `root`, connect to `127.0.0.1:port`, hello.
    pub fn connect(root: impl AsRef<Path>) -> Result<Self, Error> {
        Self::connect_named(root, DEFAULT_CLIENT_NAME)
    }

    /// Same as [`connect`] with an explicit `client_name` label (not a privilege).
    pub fn connect_named(
        root: impl AsRef<Path>,
        client_name: impl Into<String>,
    ) -> Result<Self, Error> {
        let endpoint = endpoint::load_live_endpoint(root)?;
        Self::connect_endpoint(endpoint, client_name.into())
    }

    /// Connect using an already-loaded live endpoint.
    pub fn connect_endpoint(
        endpoint: Endpoint,
        client_name: impl Into<String>,
    ) -> Result<Self, Error> {
        if !endpoint::pid_is_alive(endpoint.pid) {
            return Err(Error::Stale { pid: endpoint.pid });
        }
        // I8: bus is 127.0.0.1 only — ignore any other host written on disk.
        let addr = SocketAddr::from(([127, 0, 0, 1], endpoint.port));
        let stream = TcpStream::connect_timeout(&addr, CONNECT_TIMEOUT)?;
        stream.set_nodelay(true)?;
        stream.set_read_timeout(Some(IO_TIMEOUT))?;
        stream.set_write_timeout(Some(IO_TIMEOUT))?;
        let reader = BufReader::new(stream.try_clone()?);
        let mut client = Self {
            writer: stream,
            reader,
            endpoint,
            hello: HelloInfo {
                actor_id: String::new(),
                principal: String::new(),
                protocol_ver: PROTOCOL_VER.to_owned(),
                result: Value::Null,
            },
            next_id: AtomicU64::new(1),
        };
        let hello = client.perform_hello(client_name.into())?;
        client.hello = hello;
        Ok(client)
    }

    pub fn actor_id(&self) -> &str {
        &self.hello.actor_id
    }

    pub fn principal(&self) -> &str {
        &self.hello.principal
    }

    pub fn host(&self) -> &str {
        "127.0.0.1"
    }

    pub fn port(&self) -> u16 {
        self.endpoint.port
    }

    pub fn hello(&self) -> &HelloInfo {
        &self.hello
    }

    /// Endpoint used for this connection. `Debug` redacts the token.
    pub fn endpoint(&self) -> &Endpoint {
        &self.endpoint
    }

    /// JSON-RPC call. Auto-inserts `command_id` for mutating/job methods.
    /// Transport failures become [`RpcError`] (`E_IO`) — never panic.
    pub fn call(&mut self, method: &str, params: Value) -> Result<Value, RpcError> {
        self.invoke(method, params).map(|invoked| invoked.result)
    }

    /// Like [`call`], but also returns the `command_id` that was sent / generated.
    pub fn invoke(&mut self, method: &str, params: Value) -> Result<InvokeResult, RpcError> {
        if method == "session.hello" {
            return Ok(InvokeResult {
                command_id: None,
                result: self.hello.result.clone(),
            });
        }
        let (params, command_id) = ensure_command_id(method, params);
        match self.exchange(method, params) {
            Ok(result) => Ok(InvokeResult { command_id, result }),
            Err(Error::Rpc(err)) => Err(err),
            Err(err) => Err(err.into_rpc()),
        }
    }

    /// `session.subscribe` then wait up to `wait` for notifications.
    pub fn subscribe_and_collect(
        &mut self,
        topics: &[&str],
        wait: Duration,
    ) -> Result<Vec<Notification>, RpcError> {
        let topics: Vec<Value> = topics
            .iter()
            .map(|t| Value::String((*t).to_owned()))
            .collect();
        self.call("session.subscribe", json!({ "topics": topics }))?;
        self.collect_notifications(wait).map_err(Error::into_rpc)
    }

    fn perform_hello(&mut self, client_name: String) -> Result<HelloInfo, Error> {
        let params = json!({
            "client_name": client_name,
            "protocol_ver": PROTOCOL_VER,
            "token": self.endpoint.token(),
        });
        let result = self.exchange("session.hello", params)?;
        let actor_id = result
            .get("actor_id")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_owned();
        let principal = result
            .get("principal")
            .and_then(Value::as_str)
            .unwrap_or("agent")
            .to_owned();
        if principal == "human_ui" {
            return Err(Error::Protocol(
                "server issued human_ui over TCP (forbidden by I8 / 4.4)".into(),
            ));
        }
        if actor_id.is_empty() {
            return Err(Error::Protocol("session.hello returned no actor_id".into()));
        }
        let protocol_ver = result
            .get("protocol_ver")
            .and_then(Value::as_str)
            .unwrap_or(PROTOCOL_VER)
            .to_owned();
        Ok(HelloInfo {
            actor_id,
            principal,
            protocol_ver,
            result,
        })
    }

    fn exchange(&mut self, method: &str, params: Value) -> Result<Value, Error> {
        let response = self.call_raw(method, params)?;
        match response.error().cloned() {
            Some(err) => Err(Error::Rpc(err)),
            None => Ok(response.result().cloned().unwrap_or(Value::Null)),
        }
    }

    fn call_raw(&mut self, method: &str, params: Value) -> Result<Response, Error> {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let request = Request::new(id as i64, method, params);
        write_ndjson_line(&mut self.writer, &request)?;
        self.writer.flush()?;
        loop {
            let line = read_ndjson_line(&mut self.reader)?;
            match decode_message(&line)? {
                Message::Response(response) => return Ok(response),
                Message::Notification(_) => continue,
                Message::Request(_) => {
                    return Err(Error::Protocol("server sent a request".into()));
                }
            }
        }
    }

    fn collect_notifications(&mut self, wait: Duration) -> Result<Vec<Notification>, Error> {
        self.reader.get_ref().set_read_timeout(Some(wait))?;
        let mut out = Vec::new();
        loop {
            match read_ndjson_line(&mut self.reader) {
                Ok(line) => match decode_message(&line)? {
                    Message::Notification(note) => out.push(note),
                    Message::Response(_) | Message::Request(_) => {}
                },
                Err(gs_protocol::ProtocolError::Io(err))
                    if err.kind() == std::io::ErrorKind::TimedOut
                        || err.kind() == std::io::ErrorKind::WouldBlock =>
                {
                    break;
                }
                Err(gs_protocol::ProtocolError::Eof) => break,
                Err(err) => return Err(err.into()),
            }
        }
        let _ = self.reader.get_ref().set_read_timeout(Some(IO_TIMEOUT));
        Ok(out)
    }
}

impl Drop for BusClient {
    fn drop(&mut self) {
        let _ = self.writer.shutdown(Shutdown::Both);
    }
}
