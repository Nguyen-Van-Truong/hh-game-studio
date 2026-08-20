use thiserror::Error;

/// Failures while projecting a frozen scene or selecting a play camera.
#[derive(Debug, Error)]
pub enum Error {
    #[error("GS-EC-29: no active Camera2D in the play world")]
    NoActiveCamera,
    #[error(transparent)]
    Scene(#[from] gs_scene::Error),
    #[error("invalid scene: {0}")]
    InvalidScene(String),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error("luau host failed: {0}")]
    LuauHost(String),
}
