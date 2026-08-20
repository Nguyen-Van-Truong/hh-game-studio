//! MCP server: registry tools + convenience wrappers over the editor bus.

use std::path::{Path, PathBuf};

use gs_cli::{ensure_command_id, BusClient, Error as CliError, RpcError};
use rmcp::handler::server::tool::ToolRouter;
use rmcp::handler::server::wrapper::Parameters;
use rmcp::model::CallToolResult;
use rmcp::{schemars, tool, tool_handler, tool_router, ServerHandler};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::tools::{merge_registry_tools, screenshot_from_bus_ok};
use crate::{parse_cli, Cli, DEFAULT_CLIENT_NAME};

/// Input for generic `gs_command` (MASTER 10.4).
#[derive(Debug, Clone, Deserialize, Serialize, schemars::JsonSchema)]
pub struct GsCommandParams {
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

/// `obs.screenshot` convenience input.
#[derive(Debug, Clone, Default, Deserialize, Serialize, schemars::JsonSchema)]
pub struct GsScreenshotParams {
    #[serde(default)]
    pub play_id: Option<String>,
    #[serde(default)]
    pub camera: Option<Value>,
    #[serde(default)]
    pub max_size: Option<u32>,
}

/// `obs.events` convenience input (`after_seq` defaults to 0).
#[derive(Debug, Clone, Default, Deserialize, Serialize, schemars::JsonSchema)]
pub struct GsEventsPollParams {
    #[serde(default)]
    pub play_id: Option<String>,
    #[serde(default)]
    pub after_seq: u64,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub limit: Option<u64>,
}

/// `judge.run_test` convenience input.
#[derive(Debug, Clone, Deserialize, Serialize, schemars::JsonSchema)]
pub struct GsRunTestParams {
    pub gtest_rel: String,
    /// Optional ULID. If omitted, the bus client fills one (I11).
    #[serde(default)]
    pub command_id: Option<String>,
}

/// stdio MCP server. Holds the project root used to locate `endpoint.json`.
#[derive(Debug, Clone)]
pub struct GsMcp {
    root: PathBuf,
    client_name: String,
}

impl Default for GsMcp {
    fn default() -> Self {
        Self::from_cli(parse_cli(std::iter::empty()))
    }
}

impl GsMcp {
    pub fn from_cli(cli: Cli) -> Self {
        Self {
            root: cli.root,
            client_name: cli.client_name,
        }
    }

    pub fn from_args(args: impl IntoIterator<Item = String>) -> Self {
        Self::from_cli(parse_cli(args))
    }

    pub fn with_root(root: impl AsRef<Path>) -> Self {
        Self {
            root: root.as_ref().to_path_buf(),
            client_name: DEFAULT_CLIENT_NAME.into(),
        }
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    /// Combined router: convenience tools + one tool per [`gs_registry`] method.
    pub fn tool_router() -> ToolRouter<Self> {
        let mut router = Self::convenience_router();
        merge_registry_tools(&mut router);
        router
    }

    pub fn forward(&self, method: &str, params: Value) -> CallToolResult {
        match self.call_bus(method, params) {
            Ok(value) => CallToolResult::structured(value),
            Err(result) => result,
        }
    }

    fn call_bus(&self, method: &str, params: Value) -> Result<Value, CallToolResult> {
        let (params, _) = ensure_command_id(method, params);
        let mut client = BusClient::connect_named(&self.root, self.client_name.as_str())
            .map_err(connect_error_result)?;
        client.call(method, params).map_err(rpc_error_result)
    }
}

#[tool_router(router = convenience_router)]
impl GsMcp {
    #[tool(
        name = "gs_command",
        description = "Forward {method, params} JSON to the editor bus. Method names are generated from gs-registry."
    )]
    pub fn gs_command(
        &self,
        Parameters(GsCommandParams { method, params }): Parameters<GsCommandParams>,
    ) -> CallToolResult {
        self.forward(&method, params)
    }

    #[tool(
        name = "gs_screenshot",
        description = "obs.screenshot. Returns PNG image content when a real capture exists. no_gpu is a structured error — never a placeholder image."
    )]
    pub fn gs_screenshot(
        &self,
        Parameters(params): Parameters<GsScreenshotParams>,
    ) -> CallToolResult {
        match self.call_bus("obs.screenshot", screenshot_params(params)) {
            Ok(value) => screenshot_from_bus_ok(value),
            Err(result) => result,
        }
    }

    #[tool(
        name = "gs_events_poll",
        description = "obs.events after_seq — durable play event trace, not a live stream."
    )]
    pub fn gs_events_poll(
        &self,
        Parameters(params): Parameters<GsEventsPollParams>,
    ) -> CallToolResult {
        self.forward("obs.events", events_params(params))
    }

    #[tool(
        name = "gs_run_test",
        description = "judge.run_test — run a .gtest.json and return the evidence bundle path."
    )]
    pub fn gs_run_test(&self, Parameters(params): Parameters<GsRunTestParams>) -> CallToolResult {
        let mut body = json!({ "gtest_rel": params.gtest_rel });
        if let Some(command_id) = params.command_id {
            body["command_id"] = json!(command_id);
        }
        self.forward("judge.run_test", body)
    }
}

#[tool_handler(
    name = "gs-mcp",
    version = "0.1.0",
    instructions = "HH Game Studio MCP. Tool list is generated from gs-registry. Use gs_command for any bus method. Convenience: gs_screenshot, gs_events_poll, gs_run_test. Locate the editor via .gs/runtime/endpoint.json under GS_ROOT or --root. Do not write secrets to stdout."
)]
impl ServerHandler for GsMcp {}

fn screenshot_params(params: GsScreenshotParams) -> Value {
    let mut map = serde_json::Map::new();
    if let Some(play_id) = params.play_id {
        map.insert("play_id".into(), json!(play_id));
    }
    if let Some(camera) = params.camera {
        map.insert("camera".into(), camera);
    }
    if let Some(max_size) = params.max_size {
        map.insert("max_size".into(), json!(max_size));
    }
    Value::Object(map)
}

fn events_params(params: GsEventsPollParams) -> Value {
    let mut map = serde_json::Map::new();
    map.insert("after_seq".into(), json!(params.after_seq));
    if let Some(play_id) = params.play_id {
        map.insert("play_id".into(), json!(play_id));
    }
    if let Some(name) = params.name {
        map.insert("name".into(), json!(name));
    }
    if let Some(limit) = params.limit {
        map.insert("limit".into(), json!(limit));
    }
    Value::Object(map)
}

fn rpc_error_result(err: RpcError) -> CallToolResult {
    let mut value = json!({
        "code": err.code,
        "message": err.message,
    });
    if let Some(data) = &err.data {
        value["app_code"] = json!(data.app_code);
        if let Some(field) = &data.field {
            value["field"] = json!(field);
        }
        if let Some(reason) = &data.reason {
            value["reason"] = json!(reason);
        }
        if let Some(retryable) = data.retryable {
            value["retryable"] = json!(retryable);
        }
    }
    CallToolResult::structured_error(value)
}

fn connect_error_result(err: CliError) -> CallToolResult {
    match err {
        CliError::Rpc(rpc) => rpc_error_result(rpc),
        other => CallToolResult::structured_error(json!({
            "app_code": "E_IO",
            "message": other.to_string(),
        })),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn start_bus() -> (TempDir, gs_editor::BusHandle) {
        let dir = TempDir::new().expect("tempdir");
        let bus = gs_editor::start(dir.path()).expect("start bus");
        (dir, bus)
    }

    #[test]
    fn hello_server_info() {
        let info = GsMcp::default().get_info();
        assert_eq!(info.server_info.name, crate::SERVER_NAME);
        assert_eq!(info.server_info.version, "0.1.0");
        assert!(info.capabilities.tools.is_some());
    }

    #[test]
    fn gs_command_session_ping_returns_ok() {
        let (dir, _bus) = start_bus();
        let mcp = GsMcp::with_root(dir.path());
        let result = mcp.gs_command(Parameters(GsCommandParams {
            method: "session.ping".into(),
            params: json!({}),
        }));
        assert_ne!(result.is_error, Some(true), "{result:?}");
        let value = result.structured_content.expect("structured ping");
        assert_eq!(value["ok"], true);
    }

    #[test]
    fn live_secret_absent_from_tool_list_and_ping() {
        let (dir, bus) = start_bus();
        let secret = bus.endpoint().token().to_owned();
        assert!(!secret.is_empty());
        let mcp = GsMcp::with_root(dir.path());
        let tools = serde_json::to_string(&GsMcp::tool_router().list_all()).expect("tools");
        assert!(!tools.contains(&secret));
        let result = mcp.gs_command(Parameters(GsCommandParams {
            method: "session.ping".into(),
            params: json!({}),
        }));
        let blob = format!(
            "{:?}{}",
            result,
            result
                .structured_content
                .as_ref()
                .map(ToString::to_string)
                .unwrap_or_default()
        );
        assert!(!blob.contains(&secret));
    }

    #[test]
    fn gs_command_forwards_unknown_registry_style_method() {
        let (dir, _bus) = start_bus();
        let mcp = GsMcp::with_root(dir.path());
        let result = mcp.gs_command(Parameters(GsCommandParams {
            method: "entity.spawn".into(),
            params: json!({ "name": "crate" }),
        }));
        assert_eq!(result.is_error, Some(true));
        let text = crate::first_text(&result).unwrap_or("");
        assert!(
            !text.contains("tool not found"),
            "must reach the bus, got {text}"
        );
    }
}
