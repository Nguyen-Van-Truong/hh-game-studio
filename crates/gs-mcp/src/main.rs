//! stdio MCP server. Do not write logs to stdout (I8).

use gs_mcp::GsMcp;
use rmcp::{transport::stdio, ServiceExt};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let server = GsMcp::from_args(std::env::args().skip(1));
    let running = server.serve(stdio()).await?;
    running.waiting().await?;
    Ok(())
}
