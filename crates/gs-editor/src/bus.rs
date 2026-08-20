//! TCP command bus: 127.0.0.1 + token, NDJSON JSON-RPC (MASTER 4.1 / I8).

use std::io::{self, BufReader, Read, Write};
use std::net::{Shutdown, SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::sync_channel;
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use gs_protocol::{
    decode_message, read_ndjson_line, write_ndjson_line, ErrorData, Id, Message, Notification,
    Request, Response, RpcError, IDLE_TIMEOUT_SECS, INVALID_REQUEST, MAX_LINE_BYTES, PROTOCOL_VER,
    SLOWLORIS_SECS, UNAUTHORIZED,
};
use serde_json::{json, Value};
use ulid::Ulid;

use crate::editor::{CallContext, Editor, Outbound, HUMAN_UI_ID};
use crate::endpoint::{self, Endpoint};
use crate::error::{invalid_params, unauthorized, Error};
use crate::gizmo::{GizmoDrag, GizmoDragUpdate, GizmoKind};
use crate::hierarchy::HierarchyNode;
use crate::inspector::InspectorView;
use crate::snapshot::{ProjectChrome, ViewportEntity};
use crate::types::{FeedEntry, Principal, SessionPanel};

type Shared = Arc<Mutex<Editor>>;

/// Running bus: TCP accept loop + in-process `human_ui` handle.
pub struct BusHandle {
    endpoint: Endpoint,
    endpoint_path: PathBuf,
    addr: SocketAddr,
    ui: UiHandle,
    shutdown: Arc<AtomicBool>,
    accept: Option<JoinHandle<()>>,
}

impl BusHandle {
    pub fn start(runtime_root: impl AsRef<Path>) -> Result<Self, Error> {
        let runtime_root = runtime_root.as_ref();
        endpoint::cleanup_stale(runtime_root)?;

        let listener = TcpListener::bind(("127.0.0.1", 0))?;
        listener.set_nonblocking(true)?;
        let addr = listener.local_addr()?;
        let token = generate_token();
        let endpoint = Endpoint::new("127.0.0.1", addr.port(), token, std::process::id());
        let endpoint_path = endpoint::write_file(runtime_root, &endpoint)?;

        let core: Shared = Arc::new(Mutex::new(Editor::new(runtime_root.to_path_buf())));
        let ui = UiHandle {
            core: Arc::clone(&core),
        };
        let shutdown = Arc::new(AtomicBool::new(false));
        let accept_flag = Arc::clone(&shutdown);
        let accept_core = Arc::clone(&core);
        let accept_token = Arc::new(endpoint.token().to_owned());
        let accept = thread::Builder::new()
            .name("gs-editor-accept".into())
            .spawn(move || accept_loop(listener, accept_core, accept_flag, accept_token))?;

        Ok(Self {
            endpoint,
            endpoint_path,
            addr,
            ui,
            shutdown,
            accept: Some(accept),
        })
    }

    pub fn endpoint(&self) -> &Endpoint {
        &self.endpoint
    }

    pub fn endpoint_path(&self) -> &Path {
        &self.endpoint_path
    }

    pub fn local_addr(&self) -> SocketAddr {
        self.addr
    }

    /// In-process UI dispatcher (`principal: human_ui`). Never issued over TCP.
    pub fn ui(&self) -> &UiHandle {
        &self.ui
    }

    /// TCP `session.hello` as an agent. `client_name` is a label only (GS-EC-15).
    pub fn connect_agent(&self, client_name: impl Into<String>) -> Result<AgentClient, Error> {
        AgentClient::hello(self.addr, self.endpoint.token(), client_name.into())
    }
}

impl Drop for BusHandle {
    fn drop(&mut self) {
        self.shutdown.store(true, Ordering::SeqCst);
        let _ = TcpStream::connect(self.addr);
        if let Some(handle) = self.accept.take() {
            let _ = handle.join();
        }
        let _ = std::fs::remove_file(&self.endpoint_path);
    }
}

/// In-process handle used by the editor window (and tests) as `human_ui`.
#[derive(Clone)]
pub struct UiHandle {
    core: Shared,
}

impl UiHandle {
    pub fn actor_id(&self) -> &'static str {
        HUMAN_UI_ID
    }

    pub fn principal(&self) -> Principal {
        Principal::HumanUi
    }

    pub fn call(&self, method: &str, params: Value) -> Result<Value, RpcError> {
        let mut editor = lock(&self.core);
        editor.handle(
            CallContext {
                actor_id: HUMAN_UI_ID,
                principal: Principal::HumanUi,
                skip_confirm: false,
            },
            method,
            params,
        )
    }

    pub fn feed(&self) -> Vec<FeedEntry> {
        lock(&self.core).feed().to_vec()
    }

    pub fn notifications(&self) -> Vec<Notification> {
        lock(&self.core).notifications().to_vec()
    }

    pub fn session_panel(&self) -> SessionPanel {
        lock(&self.core).session_panel()
    }

    pub fn heuristic_log(&self) -> Vec<String> {
        lock(&self.core).heuristic_log().to_vec()
    }

    /// Read-only chrome for the 5-region shell. Does not dispatch.
    pub fn project_chrome(&self) -> ProjectChrome {
        lock(&self.core).project_chrome()
    }

    /// Document entities for the viewport. Empty when no project is open.
    /// While a gizmo drag is open, the dragged entity shows the preview pose.
    pub fn viewport_entities(&self) -> Vec<ViewportEntity> {
        lock(&self.core).viewport_entities_with_preview()
    }

    /// Hierarchy forest `{id, name, parent, order, children[]}` from the open document.
    pub fn hierarchy(&self) -> Vec<HierarchyNode> {
        lock(&self.core).hierarchy_tree()
    }

    /// Schema-driven inspector fields + current values for one entity.
    pub fn inspector(&self, entity_id: impl AsRef<str>) -> Result<InspectorView, RpcError> {
        lock(&self.core).inspector_view(entity_id.as_ref())
    }

    /// Start a human gizmo drag. Soft-locks the entity for 2s (renewed on update).
    /// Preview only — does not dispatch.
    pub fn begin_gizmo_drag(
        &self,
        entity_id: impl AsRef<str>,
        kind: GizmoKind,
    ) -> Result<(), RpcError> {
        lock(&self.core).begin_gizmo_drag(entity_id.as_ref(), kind)
    }

    /// Update the in-memory preview. Does **not** dispatch (no WAL / revision).
    pub fn update_gizmo_drag(&self, update: GizmoDragUpdate) -> Result<(), RpcError> {
        lock(&self.core).update_gizmo_drag(update)
    }

    /// Commit the preview as one `component.set` via the dispatcher (I1 / 2.8).
    /// Feed badge is Human; label is `gizmo move` / rotate / scale.
    pub fn end_gizmo_drag(&self) -> Result<Value, RpcError> {
        let mut editor = lock(&self.core);
        editor.end_gizmo_drag(CallContext {
            actor_id: HUMAN_UI_ID,
            principal: Principal::HumanUi,
            skip_confirm: false,
        })
    }

    /// Open drag, if any (preview is not on the document until [`Self::end_gizmo_drag`]).
    pub fn gizmo_drag(&self) -> Option<GizmoDrag> {
        lock(&self.core).gizmo_drag()
    }

    /// Last play world dump as JSON, throttled to 10 Hz. No window required.
    pub fn live_view_snapshot(&self) -> Result<Value, RpcError> {
        lock(&self.core).live_view_snapshot()
    }

    /// Poll `scripts/*.luau` mtimes (no `notify` crate). Ingest or conflict.
    pub fn poll_script_watcher(&self) -> Result<Value, RpcError> {
        lock(&self.core).poll_script_watcher()
    }
}

/// One TCP agent after a successful `session.hello`.
pub struct AgentClient {
    writer: TcpStream,
    reader: BufReader<TcpStream>,
    actor_id: String,
    principal: String,
    next_id: AtomicU64,
}

impl AgentClient {
    fn hello(addr: SocketAddr, token: &str, client_name: String) -> Result<Self, Error> {
        let stream = TcpStream::connect(addr)?;
        stream.set_nodelay(true)?;
        stream.set_read_timeout(Some(Duration::from_secs(10)))?;
        stream.set_write_timeout(Some(Duration::from_secs(10)))?;
        let reader = BufReader::new(stream.try_clone()?);
        let mut client = Self {
            writer: stream,
            reader,
            actor_id: String::new(),
            principal: String::new(),
            next_id: AtomicU64::new(1),
        };
        let result = client.call(
            "session.hello",
            json!({
                "client_name": client_name,
                "protocol_ver": PROTOCOL_VER,
                "token": token,
            }),
        )?;
        client.actor_id = result
            .get("actor_id")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_owned();
        client.principal = result
            .get("principal")
            .and_then(Value::as_str)
            .unwrap_or("agent")
            .to_owned();
        if client.principal == "human_ui" {
            return Err(Error::Protocol(
                "server issued human_ui over TCP (forbidden by I8 / 4.4)".into(),
            ));
        }
        Ok(client)
    }

    pub fn actor_id(&self) -> &str {
        &self.actor_id
    }

    pub fn principal(&self) -> &str {
        &self.principal
    }

    pub fn call(&mut self, method: &str, params: Value) -> Result<Value, RpcError> {
        let response = self.call_raw(method, params).map_err(|err| {
            RpcError::with_data(INVALID_REQUEST, err.to_string(), ErrorData::new("E_IO"))
        })?;
        match response.error().cloned() {
            Some(err) => Err(err),
            None => Ok(response.result().cloned().unwrap_or(Value::Null)),
        }
    }

    pub fn call_raw(&mut self, method: &str, params: Value) -> Result<Response, Error> {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let request = Request::new(id as i64, method, params);
        write_ndjson_line(&mut self.writer, &request)
            .map_err(|err| Error::Protocol(err.to_string()))?;
        self.writer.flush()?;
        loop {
            let line = read_ndjson_line(&mut self.reader)
                .map_err(|err| Error::Protocol(err.to_string()))?;
            match decode_message(&line).map_err(|err| Error::Protocol(err.to_string()))? {
                Message::Response(response) => return Ok(response),
                Message::Notification(_) => continue,
                Message::Request(_) => {
                    return Err(Error::Protocol("server sent a request".into()));
                }
            }
        }
    }
}

impl Drop for AgentClient {
    fn drop(&mut self) {
        let _ = self.writer.shutdown(Shutdown::Both);
    }
}

fn accept_loop(listener: TcpListener, core: Shared, shutdown: Arc<AtomicBool>, token: Arc<String>) {
    while !shutdown.load(Ordering::SeqCst) {
        match listener.accept() {
            Ok((stream, _)) => {
                if shutdown.load(Ordering::SeqCst) {
                    break;
                }
                let core = Arc::clone(&core);
                let shutdown = Arc::clone(&shutdown);
                let token = Arc::clone(&token);
                let _ = thread::Builder::new()
                    .name("gs-editor-conn".into())
                    .spawn(move || handle_connection(stream, core, shutdown, token));
            }
            Err(err) if err.kind() == io::ErrorKind::WouldBlock => {
                thread::sleep(Duration::from_millis(20));
            }
            Err(_) => {
                if shutdown.load(Ordering::SeqCst) {
                    break;
                }
                thread::sleep(Duration::from_millis(50));
            }
        }
    }
}

fn handle_connection(
    stream: TcpStream,
    core: Shared,
    shutdown: Arc<AtomicBool>,
    token: Arc<String>,
) {
    let _ = stream.set_nodelay(true);
    let _ = stream.set_read_timeout(Some(Duration::from_millis(200)));
    let Ok(writer_stream) = stream.try_clone() else {
        return;
    };
    let (tx, rx) = sync_channel::<Outbound>(64);
    let write_thread = thread::spawn(move || {
        let mut writer = writer_stream;
        while let Ok(msg) = rx.recv() {
            let result = match &msg {
                Outbound::Response(response) => write_ndjson_line(&mut writer, response),
                Outbound::Notification(notification) => {
                    write_ndjson_line(&mut writer, notification)
                }
            };
            if result.is_err() || writer.flush().is_err() {
                break;
            }
        }
        let _ = writer.shutdown(Shutdown::Write);
    });

    let mut reader = BufReader::new(stream);
    let mut identity: Option<String> = None;

    while !shutdown.load(Ordering::SeqCst) {
        match read_line_timed(&mut reader, identity.is_some()) {
            ReadOutcome::Line(line) => {
                if let Some(close) = process_line(&core, &tx, &mut identity, &line, &token) {
                    if close {
                        break;
                    }
                }
            }
            ReadOutcome::Idle | ReadOutcome::Eof | ReadOutcome::Proto(None) => break,
            ReadOutcome::Proto(Some(err)) => {
                let _ = tx.send(Outbound::Response(Response::err(0_i64, err)));
                break;
            }
        }
        if let Some(actor_id) = &identity {
            if lock(&core).is_revoked(actor_id) {
                break;
            }
        }
    }

    if let Some(actor_id) = identity {
        lock(&core).disconnect_agent(&actor_id);
    }
    drop(tx);
    let _ = write_thread.join();
}

fn process_line(
    core: &Shared,
    tx: &std::sync::mpsc::SyncSender<Outbound>,
    identity: &mut Option<String>,
    line: &[u8],
    token: &str,
) -> Option<bool> {
    match decode_message(line) {
        Ok(Message::Request(request)) => {
            let close = dispatch_request(core, tx, identity, request, token);
            Some(close)
        }
        Ok(Message::Notification(_)) => None,
        Ok(Message::Response(_)) => None,
        Err(err) => {
            let rpc =
                RpcError::from_protocol(&err).unwrap_or_else(|| RpcError::proto(err.to_string()));
            let _ = tx.send(Outbound::Response(Response::err(peek_id(line), rpc)));
            Some(err.app_code() == Some(gs_protocol::APP_CODE_PROTO))
        }
    }
}

fn dispatch_request(
    core: &Shared,
    tx: &std::sync::mpsc::SyncSender<Outbound>,
    identity: &mut Option<String>,
    request: Request,
    token: &str,
) -> bool {
    let id = request.id.clone();
    let method = request.method.clone();
    let params = request.params;

    if identity.is_none() {
        if method != "session.hello" {
            let _ = tx.send(Outbound::Response(Response::err(
                id,
                unauthorized("first RPC must be session.hello"),
            )));
            return true;
        }
        match perform_hello(core, tx.clone(), params, token) {
            Ok((actor_id, result)) => {
                *identity = Some(actor_id);
                let _ = tx.send(Outbound::Response(Response::ok(id, result)));
                return false;
            }
            Err(err) => {
                let _ = tx.send(Outbound::Response(Response::err(id, err)));
                return true;
            }
        }
    }

    let actor_id = identity.as_deref().unwrap_or("").to_owned();
    let result = {
        let mut editor = lock(core);
        editor.handle(
            CallContext {
                actor_id: &actor_id,
                principal: Principal::Agent,
                skip_confirm: false,
            },
            &method,
            params,
        )
    };
    let response = match result {
        Ok(value) => Response::ok(id, value),
        Err(err) => Response::err(id, err),
    };
    let _ = tx.send(Outbound::Response(response));
    method == "session.goodbye"
}

fn perform_hello(
    core: &Shared,
    tx: std::sync::mpsc::SyncSender<Outbound>,
    params: Value,
    expected_token: &str,
) -> Result<(String, Value), RpcError> {
    let obj = match params {
        Value::Null => return Err(invalid_params("session.hello requires params")),
        Value::Object(map) => map,
        _ => return Err(invalid_params("session.hello params must be an object")),
    };
    let client_name = obj
        .get("client_name")
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| invalid_params("missing client_name"))?
        .to_owned();
    let protocol_ver = obj
        .get("protocol_ver")
        .and_then(Value::as_str)
        .ok_or_else(|| invalid_params("missing protocol_ver"))?;
    if protocol_ver != PROTOCOL_VER {
        return Err(invalid_params(format!(
            "unsupported protocol_ver {protocol_ver}"
        )));
    }
    let offered = obj.get("token").and_then(Value::as_str).unwrap_or("");
    if expected_token.is_empty() || !tokens_eq(offered, expected_token) {
        return Err(RpcError::with_data(
            UNAUTHORIZED,
            "invalid or missing token",
            ErrorData::new("E_UNAUTHORIZED"),
        ));
    }
    let mut editor = lock(core);
    let result = editor.register_agent(client_name, tx);
    let actor_id = result
        .get("actor_id")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_owned();
    Ok((actor_id, result))
}

fn tokens_eq(a: &str, b: &str) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.bytes()
        .zip(b.bytes())
        .fold(0u8, |acc, (x, y)| acc | (x ^ y))
        == 0
}

enum ReadOutcome {
    Line(Vec<u8>),
    Idle,
    Eof,
    Proto(Option<RpcError>),
}

fn read_line_timed(reader: &mut BufReader<TcpStream>, allow_idle: bool) -> ReadOutcome {
    let mut buf = Vec::new();
    let line_start = Instant::now();
    let mut last_byte = Instant::now();
    let mut any = false;
    let slow = Duration::from_secs(SLOWLORIS_SECS);
    let idle = Duration::from_secs(IDLE_TIMEOUT_SECS);
    loop {
        let mut byte = [0u8; 1];
        match reader.read(&mut byte) {
            Ok(0) => return ReadOutcome::Eof,
            Ok(_) => {
                any = true;
                last_byte = Instant::now();
                if byte[0] == b'\n' {
                    if buf.len() > MAX_LINE_BYTES {
                        return ReadOutcome::Proto(Some(RpcError::proto(
                            "NDJSON line exceeds MAX_LINE_BYTES",
                        )));
                    }
                    return ReadOutcome::Line(buf);
                }
                buf.push(byte[0]);
                if buf.len() > MAX_LINE_BYTES {
                    return ReadOutcome::Proto(Some(RpcError::proto(
                        "NDJSON line exceeds MAX_LINE_BYTES",
                    )));
                }
                if line_start.elapsed() > slow {
                    return ReadOutcome::Proto(Some(RpcError::proto("slowloris: line incomplete")));
                }
            }
            Err(err)
                if err.kind() == io::ErrorKind::WouldBlock
                    || err.kind() == io::ErrorKind::TimedOut =>
            {
                if any && line_start.elapsed() > slow {
                    return ReadOutcome::Proto(Some(RpcError::proto("slowloris: line incomplete")));
                }
                if !any && allow_idle && last_byte.elapsed() > idle {
                    return ReadOutcome::Idle;
                }
                if !any && !allow_idle && line_start.elapsed() > slow {
                    return ReadOutcome::Proto(Some(RpcError::proto("slowloris: no hello")));
                }
            }
            Err(_) => return ReadOutcome::Eof,
        }
    }
}

fn peek_id(bytes: &[u8]) -> Id {
    if let Ok(value) = serde_json::from_slice::<Value>(bytes) {
        if let Some(id) = value.get("id") {
            if let Some(s) = id.as_str() {
                return Id::from(s);
            }
            if let Some(n) = id.as_i64() {
                return Id::from(n);
            }
        }
    }
    Id::from(0_i64)
}

fn generate_token() -> String {
    format!("{}{}", Ulid::new(), Ulid::new())
}

fn lock(core: &Shared) -> std::sync::MutexGuard<'_, Editor> {
    core.lock().unwrap_or_else(|err| err.into_inner())
}
