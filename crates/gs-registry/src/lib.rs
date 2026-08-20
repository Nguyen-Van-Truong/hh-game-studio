//! Executable method registry (MASTER 4.0). This crate is the source of truth.
//!
//! Handlers land in later work packages. This crate only declares the contract
//! and generates `docs/PROTOCOL.md`.

mod catalog;
mod docs;
mod spec;

pub use docs::{generate_protocol_md, write_protocol_md};
pub use spec::{Capability, Idempotency, MethodSpec, SideEffect, Undo};

use std::sync::OnceLock;

static METHODS: OnceLock<Vec<MethodSpec>> = OnceLock::new();

/// All registered methods, in catalog order.
pub fn all_methods() -> &'static [MethodSpec] {
    METHODS.get_or_init(catalog::catalog)
}

/// Look up a method by exact name (`entity.spawn`, `undo.perform`, …).
pub fn get(name: &str) -> Option<&'static MethodSpec> {
    all_methods().iter().find(|spec| spec.name == name)
}

/// Number of registered methods.
pub fn method_count() -> usize {
    all_methods().len()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;
    use std::path::PathBuf;

    const UI_ONLY: &[&str] = &[
        "session.pause_actor",
        "session.resume_actor",
        "session.revoke",
        "capability.grant",
        "capability.revoke",
        "confirmation.approve",
        "confirmation.deny",
        "undo.perform",
        "undo.redo",
        "script.buffer_set",
        "script.conflict_resolve",
    ];

    const REQUIRED: &[&str] = &[
        "session.hello",
        "session.ping",
        "session.goodbye",
        "session.subscribe",
        "session.list",
        "session.pause_actor",
        "session.resume_actor",
        "session.revoke",
        "capability.grant",
        "capability.revoke",
        "capability.list",
        "confirmation.approve",
        "confirmation.deny",
        "project.create",
        "project.open",
        "project.info",
        "project.save_all",
        "project.settings_get",
        "project.settings_set",
        "scene.new",
        "scene.open",
        "scene.save",
        "scene.list",
        "scene.dump",
        "scene.stats",
        "entity.spawn",
        "entity.destroy",
        "entity.duplicate",
        "entity.reparent",
        "entity.set_order",
        "entity.rename",
        "entity.find",
        "entity.lock",
        "entity.unlock",
        "component.set",
        "component.add",
        "component.remove",
        "component.get",
        "component.registry",
        "blueprint.create",
        "blueprint.instantiate",
        "transaction.execute",
        "undo.perform",
        "undo.redo",
        "undo.revert_own",
        "undo.revert",
        "undo.history",
    ];

    fn repo_protocol_md() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../docs/PROTOCOL.md")
    }

    #[test]
    fn method_names_are_unique() {
        let mut seen = HashSet::new();
        for spec in all_methods() {
            assert!(
                seen.insert(spec.name),
                "duplicate method name: {}",
                spec.name
            );
        }
    }

    #[test]
    fn required_m0_methods_are_registered() {
        for name in REQUIRED {
            assert!(get(name).is_some(), "missing required method: {name}");
        }
    }

    #[test]
    fn undo_perform_is_ui_only() {
        let spec = get("undo.perform").expect("undo.perform must be registered");
        assert_eq!(spec.capability, Capability::UiOnly);
    }

    #[test]
    fn listed_ui_methods_are_ui_only() {
        for name in UI_ONLY {
            let spec = get(name).unwrap_or_else(|| panic!("missing {name}"));
            assert_eq!(spec.capability, Capability::UiOnly, "{name}");
        }
    }

    #[test]
    fn entity_destroy_is_destructive_when_mass() {
        let spec = get("entity.destroy").expect("entity.destroy");
        match spec.capability {
            Capability::Destructive(note) => {
                assert!(
                    note.contains("entity.destroy.mass"),
                    "expected mass note, got {note}"
                );
            }
            other => panic!("expected Destructive, got {other}"),
        }
    }

    #[test]
    fn generated_protocol_md_is_nonempty() {
        let md = generate_protocol_md();
        assert!(!md.is_empty());
        assert!(md.contains("entity.spawn"));
    }

    #[test]
    fn writes_protocol_md_to_repo_docs() {
        let path = repo_protocol_md();
        write_protocol_md(&path).expect("write docs/PROTOCOL.md");
        let contents = std::fs::read_to_string(&path).expect("read docs/PROTOCOL.md");
        assert!(!contents.is_empty());
        assert!(contents.contains("entity.spawn"));
    }

    #[test]
    fn get_unknown_is_none() {
        assert!(get("no.such.method").is_none());
    }

    #[test]
    fn script_document_methods_are_registered() {
        let create = get("script.create").expect("script.create");
        assert_eq!(create.side_effect, SideEffect::Mutating);
        assert_eq!(create.idempotency, Idempotency::ByCommandId);
        assert_eq!(create.undo, Undo::Auto);

        let set_source = get("script.set_source").expect("script.set_source");
        assert_eq!(set_source.side_effect, SideEffect::Mutating);
        assert_eq!(set_source.idempotency, Idempotency::ByCommandId);

        let get_source = get("script.get_source").expect("script.get_source");
        assert_eq!(get_source.side_effect, SideEffect::ReadOnly);
        assert_eq!(get_source.idempotency, Idempotency::NotApplicable);

        let ingest = get("script.ingest_external").expect("script.ingest_external");
        assert_eq!(ingest.side_effect, SideEffect::Mutating);
        assert_eq!(ingest.idempotency, Idempotency::ByCommandId);

        let reload = get("script.reload").expect("script.reload");
        assert_eq!(reload.side_effect, SideEffect::Mutating);
        assert_eq!(reload.idempotency, Idempotency::Natural);
        assert_eq!(reload.undo, Undo::None);
        assert_eq!(reload.capability, Capability::Base);
        assert!(!reload.is_ui_only());
    }

    #[test]
    fn inputmap_document_methods_are_registered() {
        let get_map = get("inputmap.get").expect("inputmap.get");
        assert_eq!(get_map.side_effect, SideEffect::ReadOnly);
        assert_eq!(get_map.idempotency, Idempotency::NotApplicable);
        assert_eq!(get_map.undo, Undo::None);

        let set_map = get("inputmap.set").expect("inputmap.set");
        assert_eq!(set_map.side_effect, SideEffect::Mutating);
        assert_eq!(set_map.idempotency, Idempotency::ByCommandId);
        assert_eq!(set_map.undo, Undo::Auto);
    }

    #[test]
    fn build_job_methods_are_registered() {
        let game = get("build.game").expect("build.game");
        assert_eq!(game.side_effect, SideEffect::Job);
        assert_eq!(game.idempotency, Idempotency::ByCommandId);

        let status = get("build.status").expect("build.status");
        assert_eq!(status.side_effect, SideEffect::ReadOnly);

        let cancel = get("build.cancel").expect("build.cancel");
        assert_eq!(cancel.side_effect, SideEffect::Mutating);
    }

    #[test]
    fn tilemap_document_methods_are_registered() {
        let set_cells = get("tilemap.set_cells").expect("tilemap.set_cells");
        assert_eq!(set_cells.side_effect, SideEffect::Mutating);
        assert_eq!(set_cells.idempotency, Idempotency::ByCommandId);
        assert_eq!(set_cells.undo, Undo::Auto);

        let fill = get("tilemap.fill_rect").expect("tilemap.fill_rect");
        assert_eq!(fill.side_effect, SideEffect::Mutating);
        assert_eq!(fill.idempotency, Idempotency::ByCommandId);
        assert_eq!(fill.undo, Undo::Auto);
    }

    #[test]
    fn method_spec_serializes() {
        let json = serde_json::to_value(get("entity.spawn").expect("entity.spawn"))
            .expect("serialize MethodSpec");
        assert_eq!(json["name"], "entity.spawn");
    }

    #[test]
    fn live_play_obs_judge_methods_are_registered() {
        const LIVE: &[&str] = &[
            "play.start",
            "play.stop",
            "play.status",
            "play.pause",
            "play.resume",
            "play.step_frames",
            "play.set_timescale",
            "input.inject",
            "obs.screenshot",
            "obs.world_dump",
            "obs.logs_tail",
            "obs.perf",
            "obs.events",
            "obs.query",
            "judge.run_until_event",
            "judge.wait_event",
            "judge.assert_world",
            "judge.assert_perf",
            "judge.assert_screenshot",
            "judge.run_test",
            "runtime.copy_to_scene",
            "artifact.list",
            "artifact.get",
            "artifact.gc",
            "asset.import",
            "asset.list",
            "script.diagnostics",
            "script.reload",
            "script.conflicts",
        ];
        for name in LIVE {
            let spec = get(name).unwrap_or_else(|| panic!("missing live method: {name}"));
            assert!(
                !spec.is_ui_only(),
                "{name} is play/agent-callable (MASTER 4.2 P), not UiOnly"
            );
        }

        let start = get("play.start").expect("play.start");
        assert_eq!(start.side_effect, SideEffect::Mutating);
        assert_eq!(start.idempotency, Idempotency::ByCommandId);
        assert_eq!(start.undo, Undo::None);

        let status = get("play.status").expect("play.status");
        assert_eq!(status.side_effect, SideEffect::ReadOnly);
        assert_eq!(status.idempotency, Idempotency::NotApplicable);

        let copy = get("runtime.copy_to_scene").expect("runtime.copy_to_scene");
        assert_eq!(copy.side_effect, SideEffect::Mutating);
        assert_eq!(copy.idempotency, Idempotency::ByCommandId);
        assert_eq!(copy.undo, Undo::Auto);

        let import = get("asset.import").expect("asset.import");
        assert_eq!(import.side_effect, SideEffect::Mutating);
        assert_eq!(import.idempotency, Idempotency::ByCommandId);
        assert_eq!(import.undo, Undo::Auto);
        assert!(
            import.errors.contains(&"E_PATH"),
            "asset.import must declare E_PATH"
        );

        let query = get("obs.query").expect("obs.query");
        assert_eq!(query.side_effect, SideEffect::ReadOnly);
    }
}
