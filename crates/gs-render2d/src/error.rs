use thiserror::Error;

/// GPU / encode failures from the three render targets.
#[derive(Debug, Error)]
pub enum Error {
    #[error("no wgpu adapter (tried PRIMARY|GL then fallback/WARP)")]
    NoAdapter,
    #[error("request_device: {0}")]
    RequestDevice(String),
    #[error("viewport size must be > 0")]
    InvalidViewport,
    #[error("readback channel: {0}")]
    Readback(String),
    #[error("map_async: {0}")]
    Map(String),
    #[error("write png: {0}")]
    Png(String),
    #[error("surface: {0}")]
    Surface(String),
}
