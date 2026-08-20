//! NDJSON stdio handshake against the spike binary (no MCP Inspector).

use std::process::Stdio;
use std::time::Duration;

use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::Command;
use tokio::time::timeout;

const READ_TIMEOUT: Duration = Duration::from_secs(10);

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
        // Ignore notifications / other messages; keep reading.
    }
}

#[tokio::test]
async fn stdio_initialize_list_tools_and_echo() {
    let exe = env!("CARGO_BIN_EXE_mcp-spike");
    let mut child = Command::new(exe)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true)
        .spawn()
        .expect("spawn mcp-spike");

    let mut stdin = child.stdin.take().expect("stdin");
    let stdout = child.stdout.take().expect("stdout");
    let mut lines = BufReader::new(stdout).lines();

    let initialize = json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": { "name": "mcp-spike-test", "version": "0.0.1" }
        }
    });
    stdin
        .write_all(format!("{initialize}\n").as_bytes())
        .await
        .unwrap();
    stdin.flush().await.unwrap();

    let init = read_response(&mut lines, 1).await;
    assert!(init.get("error").is_none(), "initialize error: {init}");
    let result = init.get("result").expect("initialize result");
    assert_eq!(
        result.pointer("/serverInfo/name"),
        Some(&json!("mcp-spike"))
    );
    assert!(
        result.pointer("/capabilities/tools").is_some(),
        "tools capability: {result}"
    );

    let initialized = json!({
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    });
    stdin
        .write_all(format!("{initialized}\n").as_bytes())
        .await
        .unwrap();

    let list = json!({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    });
    stdin
        .write_all(format!("{list}\n").as_bytes())
        .await
        .unwrap();
    stdin.flush().await.unwrap();

    let listed = read_response(&mut lines, 2).await;
    assert!(listed.get("error").is_none(), "tools/list error: {listed}");
    let tools = listed
        .pointer("/result/tools")
        .and_then(Value::as_array)
        .expect("tools array");
    let names: Vec<&str> = tools
        .iter()
        .filter_map(|t| t.get("name").and_then(Value::as_str))
        .collect();
    assert_eq!(names, vec!["gs_command"]);

    let call = json!({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "gs_command",
            "arguments": {
                "method": "session.hello",
                "params": { "ping": true }
            }
        }
    });
    stdin
        .write_all(format!("{call}\n").as_bytes())
        .await
        .unwrap();
    stdin.flush().await.unwrap();

    let called = read_response(&mut lines, 3).await;
    assert!(called.get("error").is_none(), "tools/call error: {called}");
    let structured = called.pointer("/result/structuredContent").cloned();
    let text = called
        .pointer("/result/content/0/text")
        .and_then(Value::as_str)
        .map(|s| serde_json::from_str::<Value>(s).expect("text JSON"));
    let echo = structured.or(text).expect("echo payload");
    assert_eq!(echo["method"], "session.hello");
    assert_eq!(echo["params"]["ping"], true);

    drop(stdin);
    let _ = timeout(Duration::from_secs(5), child.wait()).await;
}
