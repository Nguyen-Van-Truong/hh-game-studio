//! Production MCP server (MASTER 10.4 / T8.1).
//!
//! Tool list is generated from [`gs_registry`]. Generic [`gs_command`] plus
//! convenience wrappers talk to the editor bus the same way `gs-cli` does:
//! read `.gs/runtime/endpoint.json` under `GS_ROOT` / `--root`.

mod server;
mod tools;

pub use server::{GsCommandParams, GsEventsPollParams, GsMcp, GsRunTestParams, GsScreenshotParams};
pub use tools::{
    convenience_tool_names, encode_base64, first_text, registry_method_names,
    screenshot_from_bus_ok,
};

use std::env;
use std::path::PathBuf;

/// Convenience MCP tool names that are not bus method names.
pub const CONVENIENCE_TOOLS: &[&str] = &[
    "gs_command",
    "gs_screenshot",
    "gs_events_poll",
    "gs_run_test",
];

/// Server implementation name advertised on `initialize`.
pub const SERVER_NAME: &str = "gs-mcp";

/// Default `client_name` sent on `session.hello` (label only).
pub const DEFAULT_CLIENT_NAME: &str = "gs-mcp";

/// Resolve project root and client label from argv + `GS_ROOT` / `GS_CLIENT_NAME`.
pub fn parse_cli(args: impl IntoIterator<Item = String>) -> Cli {
    let mut root = env::var_os("GS_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));
    let mut client_name = env::var("GS_CLIENT_NAME").unwrap_or_else(|_| DEFAULT_CLIENT_NAME.into());
    let args: Vec<String> = args.into_iter().collect();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--root" => {
                i += 1;
                if let Some(value) = args.get(i) {
                    root = PathBuf::from(value);
                }
            }
            "--client-name" => {
                i += 1;
                if let Some(value) = args.get(i) {
                    client_name = value.clone();
                }
            }
            _ => {}
        }
        i += 1;
    }
    Cli { root, client_name }
}

/// Parsed `--root` / `--client-name` (and env fallbacks).
#[derive(Debug, Clone)]
pub struct Cli {
    pub root: PathBuf,
    pub client_name: String,
}

pub fn crate_name() -> &'static str {
    "gs-mcp"
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::collections::HashSet;

    #[test]
    fn smoke() {
        assert_eq!(crate_name(), "gs-mcp");
        assert_eq!(SERVER_NAME, "gs-mcp");
    }

    #[test]
    fn parse_cli_root_flag_overrides_env() {
        let parsed = parse_cli(["--root".into(), "/tmp/gs-project".into()]);
        assert_eq!(parsed.root, PathBuf::from("/tmp/gs-project"));
        assert_eq!(parsed.client_name, DEFAULT_CLIENT_NAME);
    }

    #[test]
    fn tool_list_covers_registry_and_convenience() {
        let tools = GsMcp::tool_router().list_all();
        let names: HashSet<&str> = tools.iter().map(|t| t.name.as_ref()).collect();
        for required in CONVENIENCE_TOOLS {
            assert!(
                names.contains(required),
                "missing convenience tool {required}"
            );
        }
        for method in gs_registry::all_methods() {
            assert!(
                names.contains(method.name),
                "registry method {} missing from MCP tool list",
                method.name
            );
        }
        let generated: HashSet<&str> = tools
            .iter()
            .map(|t| t.name.as_ref())
            .filter(|name| !CONVENIENCE_TOOLS.contains(name))
            .collect();
        let catalog: HashSet<&str> = gs_registry::all_methods().iter().map(|s| s.name).collect();
        assert_eq!(
            generated, catalog,
            "tool list must be generated from registry"
        );
    }

    #[test]
    fn tool_schemas_do_not_mention_bus_secret() {
        let tools = GsMcp::tool_router().list_all();
        let blob = serde_json::to_string(&tools).expect("tools json");
        let lower = blob.to_ascii_lowercase();
        assert!(
            !lower.contains("token"),
            "tool schemas/descriptions must not mention the bus secret"
        );
    }

    #[test]
    fn gs_command_schema_has_method_and_params() {
        let tools = GsMcp::tool_router().list_all();
        let tool = tools
            .iter()
            .find(|t| t.name == "gs_command")
            .expect("gs_command");
        let schema = tool.schema_as_json_value();
        let text = schema.to_string();
        assert!(text.contains("method"), "{text}");
        assert!(text.contains("params"), "{text}");
    }

    #[test]
    fn no_gpu_screenshot_is_structured_error_without_image() {
        let result = screenshot_from_bus_ok(json!({ "app_code": "no_gpu" }));
        assert_eq!(result.is_error, Some(true));
        assert!(
            result
                .content
                .iter()
                .all(|block| block.as_image().is_none()),
            "no_gpu must not invent a PNG"
        );
    }

    #[test]
    fn screenshot_without_png_path_has_no_image() {
        let result = screenshot_from_bus_ok(json!({ "note": "no file" }));
        assert_ne!(result.is_error, Some(true));
        assert!(result
            .content
            .iter()
            .all(|block| block.as_image().is_none()));
    }

    #[test]
    fn screenshot_attaches_image_when_png_exists() {
        let dir = tempfile::TempDir::new().expect("tempdir");
        let path = dir.path().join("shot.png");
        let mut bytes = vec![0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A];
        bytes.extend_from_slice(b"rest");
        std::fs::write(&path, &bytes).expect("write png");
        let result = screenshot_from_bus_ok(json!({ "path": path.to_string_lossy() }));
        assert_ne!(result.is_error, Some(true));
        let image = result
            .content
            .iter()
            .find_map(|block| block.as_image())
            .expect("image content");
        assert_eq!(image.mime_type, "image/png");
        assert_eq!(image.data, encode_base64(&bytes));
    }

    #[test]
    fn encode_base64_known_vector() {
        assert_eq!(encode_base64(b"hi"), "aGk=");
        assert_eq!(encode_base64(b"Man"), "TWFu");
    }
}
