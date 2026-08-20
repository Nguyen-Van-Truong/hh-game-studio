//! Compile-only matrix: if this crate builds, the pin set is compatible.

pub fn matrix_names() -> &'static [&'static str] {
    &[
        "egui",
        "eframe",
        "egui-wgpu",
        "wgpu",
        "winit",
        "mlua",
        "bevy_ecs",
        "rapier2d",
        "glyphon",
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crates_are_named() {
        assert_eq!(matrix_names().len(), 9);
    }

    #[test]
    fn bevy_ecs_world_constructs() {
        let _w = bevy_ecs::world::World::new();
    }

    #[test]
    fn rapier_pipeline_constructs() {
        let _p = rapier2d::pipeline::PhysicsPipeline::new();
    }
}
