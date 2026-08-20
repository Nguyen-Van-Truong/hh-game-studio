//! Authoritative project document (MASTER 5). Dispatcher is the only mutator (I1).
//!
//! WP-M0-3 slice 2: full 5.2 registry, blueprint stamp, x-unknown (I5),
//! crash (c)(d), WAL rotation + LRU dedup.

mod blueprint;
mod canonical;
mod command;
mod components;
mod document;
mod error;
mod id;
mod inputmap;
mod locks;
mod persist;
mod record;
mod script;
mod session;
mod settings;
mod tilemap;

pub use blueprint::resolve_under_root;
pub use canonical::{to_canonical_string, to_canonical_vec};
pub use command::{Command, DispatchRequest};
pub use components::{
    AnimFlipbook, AssetRef, AudioSource, Camera2D, Collider2D, ColliderShape, EntityRef,
    ExtraComponents, Name, RigidBody2D, Script, Sprite, Tags, Text2D, Tilemap, Transform2D,
    Visibility,
};
pub use document::{Document, Entity, Scene, SceneFile, DEFAULT_SCENE_ID};
pub use error::{CrashPoint, Error};
pub use id::{
    cmp_ids, format_blueprint_id, format_entity_id, parse_blueprint_id, parse_entity_id,
    parse_id_number,
};
pub use inputmap::{default_inputmap, INPUTMAP_REL};
pub use locks::{LOCK_QUOTA_PER_ACTOR, LOCK_TTL};
pub use persist::{AckCursor, Paths};
pub use record::{WalRecord, SCHEMA_VERSION};
pub use script::{DEFAULT_SCRIPT_SOURCE, DOOR_SCRIPT_SOURCE, MAX_SCRIPT_SOURCE_BYTES};
pub use session::{Ack, Dispatcher, Session};
pub use settings::default_project_settings;

pub fn crate_name() -> &'static str {
    "gs-scene"
}

#[cfg(test)]
mod tests {
    #[test]
    fn smoke() {
        assert_eq!(super::crate_name(), "gs-scene");
    }
}
