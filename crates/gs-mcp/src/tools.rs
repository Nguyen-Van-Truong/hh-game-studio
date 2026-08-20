//! MCP tool list generated from [`gs_registry`] (MASTER 10.4).

use std::sync::Arc;

use gs_registry::{Capability, Idempotency, MethodSpec, SideEffect};
use rmcp::handler::server::router::tool::ToolRoute;
use rmcp::handler::server::tool::ToolName;
use rmcp::model::{CallToolResult, ContentBlock, JsonObject, Tool, ToolAnnotations};
use serde_json::{json, Value};

use crate::server::GsMcp;

/// Names of the four non-catalog tools.
pub fn convenience_tool_names() -> &'static [&'static str] {
    crate::CONVENIENCE_TOOLS
}

/// Catalog method names, in registry order.
pub fn registry_method_names() -> Vec<&'static str> {
    gs_registry::all_methods()
        .iter()
        .map(|spec| spec.name)
        .collect()
}

/// First text block of a tool result, if any.
pub fn first_text(result: &CallToolResult) -> Option<&str> {
    result.content.iter().find_map(|block| match block {
        ContentBlock::Text(text) => Some(text.text.as_str()),
        _ => None,
    })
}

/// Description for `gs_command`, listing every registry method so the list cannot drift.
pub fn gs_command_description() -> String {
    let names = registry_method_names().join(", ");
    format!(
        "Forward {{method, params}} JSON to the editor bus (same as gs-cli). \
         Covers every gs-registry method: {names}."
    )
}

pub fn merge_registry_tools(router: &mut rmcp::handler::server::tool::ToolRouter<GsMcp>) {
    if let Some(route) = router.map.get_mut("gs_command") {
        route.attr.description = Some(gs_command_description().into());
    }
    for spec in gs_registry::all_methods() {
        router.add_route(registry_method_route(spec));
    }
}

fn registry_method_route(spec: &MethodSpec) -> ToolRoute<GsMcp> {
    let tool = Tool::new(spec.name, method_description(spec), bus_params_schema())
        .with_annotations(method_annotations(spec));
    ToolRoute::new(tool, invoke_registry_tool)
}

fn invoke_registry_tool(
    service: &GsMcp,
    ToolName(name): ToolName,
    arguments: JsonObject,
) -> CallToolResult {
    service.forward(name.as_ref(), Value::Object(arguments))
}

fn method_description(spec: &MethodSpec) -> String {
    let ui = if spec.is_ui_only() { " [UI]" } else { "" };
    format!(
        "Editor bus `{}`{ui}. side_effect={} undo={} capability={} idempotency={}. errors={}.",
        spec.name,
        spec.side_effect,
        spec.undo,
        spec.capability,
        spec.idempotency,
        spec.errors.join(",")
    )
}

fn method_annotations(spec: &MethodSpec) -> ToolAnnotations {
    ToolAnnotations::from_raw(
        None,
        Some(matches!(spec.side_effect, SideEffect::ReadOnly)),
        Some(matches!(spec.capability, Capability::Destructive(_))),
        Some(matches!(
            spec.idempotency,
            Idempotency::Natural | Idempotency::NotApplicable
        )),
        Some(false),
    )
}

fn bus_params_schema() -> Arc<JsonObject> {
    Arc::new(rmcp::model::object(json!({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": true,
    })))
}

/// Build a screenshot tool result from a successful bus payload.
///
/// Attaches MCP image content only when `path` points at a real PNG.
/// A `no_gpu` payload is a structured error and never invents image bytes.
pub fn screenshot_from_bus_ok(value: Value) -> CallToolResult {
    if value.get("app_code").and_then(Value::as_str) == Some("no_gpu") {
        return CallToolResult::structured_error(value);
    }
    let png = png_bytes_from_result(&value);
    let mut result = CallToolResult::structured(value);
    if let Some(bytes) = png {
        result
            .content
            .push(ContentBlock::image(encode_base64(&bytes), "image/png"));
    }
    result
}

fn png_bytes_from_result(value: &Value) -> Option<Vec<u8>> {
    let path = value.get("path").and_then(Value::as_str)?;
    let bytes = std::fs::read(path).ok()?;
    is_png(&bytes).then_some(bytes)
}

fn is_png(bytes: &[u8]) -> bool {
    bytes.starts_with(&[0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A])
}

/// Standard Base64 (RFC 4648) with padding. No extra crate.
pub fn encode_base64(input: &[u8]) -> String {
    const TABLE: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(input.len().div_ceil(3) * 4);
    for chunk in input.chunks(3) {
        let a = u32::from(chunk[0]);
        let b = u32::from(chunk.get(1).copied().unwrap_or(0));
        let c = u32::from(chunk.get(2).copied().unwrap_or(0));
        let n = (a << 16) | (b << 8) | c;
        out.push(TABLE[((n >> 18) & 63) as usize] as char);
        out.push(TABLE[((n >> 12) & 63) as usize] as char);
        if chunk.len() > 1 {
            out.push(TABLE[((n >> 6) & 63) as usize] as char);
        } else {
            out.push('=');
        }
        if chunk.len() > 2 {
            out.push(TABLE[(n & 63) as usize] as char);
        } else {
            out.push('=');
        }
    }
    out
}
