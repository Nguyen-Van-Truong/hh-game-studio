//! stdio MCP server for the M-1e spike. Do not write logs to stdout.

use mcp_spike::GsMcp;
use rmcp::{transport::stdio, ServiceExt};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let running = GsMcp.serve(stdio()).await?;
    running.waiting().await?;
    Ok(())
}
