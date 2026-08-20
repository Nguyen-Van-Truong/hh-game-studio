//! NDJSON stdio handshake against the gs-mcp binary (no MCP Inspector).

use std::process::Stdio;
use std::time::Duration;

use serde_json::{json, Value};
use tempfile::TempDir;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::Command;
use tokio::time::timeout;

const READ_TIMEOUT: Duration = Duration::from_secs(15);

async fn read_response(
    lines: &mut tokio::io::Lines<BufReader<tokio::process::ChildStdout>>,
    id: i64,
) -> Value {
    loop {
        let line = timeout(READ_TIMEOUT, lines.next_line())
            .await
            .unwrap_or_else(|_| panic!("timeout waiting for JSON-RPC id={id}"))
            .expect("stdout")
            .unwrap_or_else(|| panic!("EOF before JSON-RPC id={id}"));
        if line.trim().is_empty() {
            continue;
        }
        let value: Value = serde_json::from_str(&line)
            .unwrap_or_else(|e| panic!("invalid JSON from server: {e}: {line}"));
        if value.get("id") == Some(&json!(id)) {
            return value;
        }
    }
}

struct McpChild {
    child: tokio::process::Child,
    stdin: tokio::process::ChildStdin,
    lines: tokio::io::Lines<BufReader<tokio::process::ChildStdout>>,
}

fn gs_mcp_exe() -> String {
    if let Some(path) = option_env!("CARGO_BIN_EXE_gs-mcp") {
        return path.to_owned();
    }
    if let Some(path) = option_env!("CARGO_BIN_EXE_gs_mcp") {
        return path.to_owned();
    }
    for key in ["CARGO_BIN_EXE_gs-mcp", "CARGO_BIN_EXE_gs_mcp"] {
        if let Ok(path) = std::env::var(key) {
            return path;
        }
    }
    panic!("gs-mcp binary path not set (CARGO_BIN_EXE_gs-mcp)");
}

impl McpChild {
    async fn spawn(root: Option<&std::path::Path>) -> Self {
        let exe = gs_mcp_exe();
        let mut cmd = Command::new(exe);
        cmd.stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);
        if let Some(root) = root {
            cmd.arg("--root").arg(root);
            cmd.env("GS_ROOT", root);
        }
        let mut child = cmd.spawn().expect("spawn gs-mcp");
        let stdin = child.stdin.take().expect("stdin");
        let stdout = child.stdout.take().expect("stdout");
        Self {
            child,
            stdin,
            lines: BufReader::new(stdout).lines(),
        }
    }

    async fn write_json(&mut self, value: &Value) {
        self.stdin
            .write_all(format!("{value}\n").as_bytes())
            .await
            .unwrap();
        self.stdin.flush().await.unwrap();
    }

    async fn initialize(&mut self) -> Value {
        self.write_json(&json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": { "name": "gs-mcp-test", "version": "0.0.1" }
            }
        }))
        .await;
        let init = read_response(&mut self.lines, 1).await;
        assert!(init.get("error").is_none(), "initialize error: {init}");
        let result = init.get("result").expect("initialize result");
        assert_eq!(result.pointer("/serverInfo/name"), Some(&json!("gs-mcp")));
        assert!(
            result.pointer("/capabilities/tools").is_some(),
            "tools capability: {result}"
        );
        self.write_json(&json!({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }))
        .await;
        init
    }

    async fn list_tools(&mut self) -> Vec<Value> {
        self.write_json(&json!({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }))
        .await;
        let listed = read_response(&mut self.lines, 2).await;
        assert!(listed.get("error").is_none(), "tools/list error: {listed}");
        listed
            .pointer("/result/tools")
            .and_then(Value::as_array)
            .expect("tools array")
            .clone()
    }

    async fn shutdown(mut self) {
        drop(self.stdin);
        let _ = timeout(Duration::from_secs(5), self.child.wait()).await;
    }
}

fn tool_names(tools: &[Value]) -> Vec<&str> {
    tools
        .iter()
        .filter_map(|t| t.get("name").and_then(Value::as_str))
        .collect()
}

#[tokio::test]
async fn stdio_initialize_list_tools() {
    let mut mcp = McpChild::spawn(None).await;
    mcp.initialize().await;
    let tools = mcp.list_tools().await;
    let names = tool_names(&tools);
    for required in [
        "gs_command",
        "gs_screenshot",
        "gs_events_poll",
        "gs_run_test",
    ] {
        assert!(names.contains(&required), "missing {required} in {names:?}");
    }
    for spec in gs_registry::all_methods() {
        assert!(
            names.contains(&spec.name),
            "registry method {} missing from tools/list",
            spec.name
        );
    }
    let blob = serde_json::to_string(&tools).expect("tools json");
    assert!(
        !blob.to_ascii_lowercase().contains("token"),
        "tools/list must not mention the bus secret"
    );
    mcp.shutdown().await;
}

#[tokio::test]
async fn stdio_gs_command_session_ping() {
    let dir = TempDir::new().expect("tempdir");
    let bus = gs_editor::start(dir.path()).expect("start bus");
    let secret = bus.endpoint().token().to_owned();
    assert!(!secret.is_empty());

    let mut mcp = McpChild::spawn(Some(dir.path())).await;
    mcp.initialize().await;
    let tools = mcp.list_tools().await;
    let blob = serde_json::to_string(&tools).expect("tools json");
    assert!(
        !blob.contains(&secret),
        "live bus secret leaked into tools/list"
    );

    mcp.write_json(&json!({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "gs_command",
            "arguments": {
                "method": "session.ping",
                "params": {}
            }
        }
    }))
    .await;
    let called = read_response(&mut mcp.lines, 3).await;
    assert!(called.get("error").is_none(), "tools/call error: {called}");
    assert_ne!(called.pointer("/result/isError"), Some(&json!(true)));
    let structured = called.pointer("/result/structuredContent").cloned();
    let text = called
        .pointer("/result/content/0/text")
        .and_then(Value::as_str)
        .map(|s| serde_json::from_str::<Value>(s).expect("text JSON"));
    let ping = structured.or(text).expect("ping payload");
    assert_eq!(ping["ok"], true);
    let wire = called.to_string();
    assert!(!wire.contains(&secret), "secret leaked into tools/call");

    mcp.shutdown().await;
    drop(bus);
}
