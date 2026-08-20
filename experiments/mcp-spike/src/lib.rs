//! HH Game Studio M-1e MCP hello spike.
//!
//! One tool: `gs_command` — echoes `{method, params}`. Not a bus client.

use rmcp::{
    handler::server::wrapper::Parameters,
    model::{CallToolResult, ContentBlock},
    schemars, tool, tool_handler, tool_router, ServerHandler,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Input for the spike `gs_command` tool (MASTER 10.4 / T-1.e).
#[derive(Debug, Clone, Deserialize, Serialize, schemars::JsonSchema)]
pub struct GsCommandParams {
    pub method: String,
    pub params: Value,
}

/// Echo payload returned by `gs_command`.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, schemars::JsonSchema)]
pub struct GsCommandEcho {
    pub method: String,
    pub params: Value,
}

/// Echo `method` + `params` unchanged. Production `gs-mcp` will forward to the bus.
pub fn echo_command(method: impl Into<String>, params: Value) -> GsCommandEcho {
    GsCommandEcho {
        method: method.into(),
        params,
    }
}

/// Build the MCP tool result used on the wire (text + structured JSON).
pub fn echo_tool_result(echo: &GsCommandEcho) -> CallToolResult {
    let value = serde_json::to_value(echo).expect("GsCommandEcho is always JSON");
    let mut result = CallToolResult::structured(value.clone());
    result.content = vec![ContentBlock::text(value.to_string())];
    result
}

/// MCP server: hello + `gs_command` echo.
#[derive(Debug, Clone, Default)]
pub struct GsMcp;

#[tool_router]
impl GsMcp {
    #[tool(
        name = "gs_command",
        description = "Spike echo: returns {method, params} unchanged. Production will forward to the editor bus."
    )]
    pub fn gs_command(
        &self,
        Parameters(GsCommandParams { method, params }): Parameters<GsCommandParams>,
    ) -> CallToolResult {
        echo_tool_result(&echo_command(method, params))
    }
}

#[tool_handler(
    name = "mcp-spike",
    version = "0.1.0",
    instructions = "HH Game Studio M-1e hello spike. One tool: gs_command (echo)."
)]
impl ServerHandler for GsMcp {}

/// First text block of a tool result, if any.
pub fn first_text(result: &CallToolResult) -> Option<&str> {
    result.content.iter().find_map(|block| match block {
        ContentBlock::Text(text) => Some(text.text.as_str()),
        _ => None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn hello_server_info() {
        let info = GsMcp.get_info();
        assert_eq!(info.server_info.name, "mcp-spike");
        assert_eq!(info.server_info.version, "0.1.0");
        assert!(info.capabilities.tools.is_some());
    }

    #[test]
    fn list_tools_exposes_gs_command_schema() {
        let tools = GsMcp::tool_router().list_all();
        assert_eq!(tools.len(), 1, "spike exposes exactly one tool");
        assert!(GsMcp::tool_router().has_route("gs_command"));

        let tool = tools
            .iter()
            .find(|t| t.name == "gs_command")
            .expect("gs_command");
        let schema = tool.schema_as_json_value();
        let schema_text = schema.to_string();
        assert!(
            schema_text.contains("method"),
            "input schema must include method: {schema_text}"
        );
        assert!(
            schema_text.contains("params"),
            "input schema must include params: {schema_text}"
        );

        if let Some(props) = schema.get("properties") {
            assert!(props.get("method").is_some(), "properties.method");
            assert!(props.get("params").is_some(), "properties.params");
        }
    }

    #[test]
    fn gs_command_handler_echoes_method_and_params() {
        let method = "session.hello";
        let params = json!({ "ping": true, "n": 1 });
        let result = GsMcp.gs_command(Parameters(GsCommandParams {
            method: method.to_string(),
            params: params.clone(),
        }));

        assert_ne!(result.is_error, Some(true));
        let echo: GsCommandEcho =
            serde_json::from_value(result.structured_content.clone().expect("structured echo"))
                .expect("echo shape");
        assert_eq!(echo, echo_command(method, params.clone()));

        let text = first_text(&result).expect("text echo");
        let from_text: GsCommandEcho = serde_json::from_str(text).expect("text is JSON echo");
        assert_eq!(from_text.method, method);
        assert_eq!(from_text.params, params);
    }
}
