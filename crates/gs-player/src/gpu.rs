//! GPU / no-render mode for the play process (MASTER 6.4, GS-EC-31, GS-EC-48).

/// How the player should treat GPU access.
///
/// `GS_GPU=warp` is accepted and documented, but this crate does **not** pick a
/// wgpu WARP adapter (that would live in `gs-render2d`). On Windows it is
/// treated as no-render so CI without a GPU still simulates and dumps the world.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum GpuMode {
    /// Try a real GPU for `obs.screenshot`; failure → `app_code: no_gpu`.
    Auto,
    /// Documented CI fallback. Treated as [`Self::None`] (no WARP adapter here).
    Warp,
    /// Simulate + event trace + world_dump only. Screenshot → `no_gpu`.
    None,
}

impl GpuMode {
    pub fn parse_token(raw: &str) -> Self {
        match raw.trim().to_ascii_lowercase().as_str() {
            "none" | "off" | "no-render" | "norender" => Self::None,
            "warp" => Self::Warp,
            _ => Self::Auto,
        }
    }

    pub fn from_env() -> Self {
        std::env::var("GS_GPU")
            .ok()
            .map(|value| Self::parse_token(&value))
            .unwrap_or(Self::Auto)
    }

    /// Warp is not wired to a wgpu adapter in this crate; both force no-render.
    pub fn forces_no_render(self) -> bool {
        matches!(self, Self::None | Self::Warp)
    }
}

#[cfg(test)]
mod tests {
    use super::GpuMode;

    #[test]
    fn parse_gpu_tokens() {
        assert_eq!(GpuMode::parse_token("none"), GpuMode::None);
        assert_eq!(GpuMode::parse_token("NO-RENDER"), GpuMode::None);
        assert_eq!(GpuMode::parse_token("warp"), GpuMode::Warp);
        assert_eq!(GpuMode::parse_token("auto"), GpuMode::Auto);
        assert_eq!(GpuMode::parse_token(""), GpuMode::Auto);
    }
}
