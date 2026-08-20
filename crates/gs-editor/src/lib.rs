//! Editor bus, authority, confirmation, and eframe viewport (WP-M0-4 / WP-M1-2 / WP-M1-3 / WP-M1-4).
//!
//! Tests start the bus with [`start`] — no eframe / GPU window is required.
//! The window is [`run_native_window`] only (binary `main`).
//!
//! ```ignore
//! let bus = gs_editor::start(runtime_root)?;
//! let mut agent = bus.connect_agent("coder")?; // TCP hello, principal=agent
//! let ui = bus.ui();                           // in-process human_ui
//! ui.begin_gizmo_drag("e_000001", gs_editor::GizmoKind::Move)?;
//! ui.update_gizmo_drag(gs_editor::GizmoDragUpdate::move_by(1.0, 0.0))?;
//! ui.end_gizmo_drag()?; // one dispatcher txn; feed badge = Human
//! ```

mod analyze;
mod app;
mod artifacts;
mod assets;
mod build;
mod bus;
mod editor;
mod endpoint;
mod error;
mod evidence;
mod gizmo;
mod gtest;
mod hierarchy;
mod inspector;
mod open;
mod overlay;
mod play;
mod play_keys;
mod run_test;
mod schema;
mod scripts;
mod snapshot;
mod types;
mod view_state;

pub use app::run_native_window;
pub use bus::{AgentClient, BusHandle, UiHandle};
pub use endpoint::Endpoint;
pub use error::Error;
pub use gizmo::{gizmo_hit, GizmoDrag, GizmoDragUpdate, GizmoKind, GIZMO_LOCK_TTL};
pub use gs_protocol::{ErrorData, Notification, RpcError};
pub use hierarchy::{find_node, HierarchyNode};
pub use inspector::{InspectorComponent, InspectorField, InspectorView};
pub use open::resolve_startup_project;
pub use play::gc_play_snapshots;
pub use schema::{
    clamp_to_schema, component_specs, default_component_value, registry_json, ComponentSpec,
    FieldKind, FieldSpec, MASTER_5_2_TYPES,
};
pub use snapshot::{
    apply_live_dump, collect_tilemap_viewport_quads, collect_viewport_entities,
    document_to_snapshot, entities_to_snapshot, expand_tilemap_quads, ProjectChrome,
    ViewportEntity, TILEMAP_VIEW_QUAD_CAP,
};
pub use types::{ActorInfo, Badge, FeedEntry, PendingConfirmation, Principal, SessionPanel};
pub use view_state::{apply_view_navigation, world_to_pixel, ViewState};

use std::path::Path;

/// Bind `127.0.0.1` (ephemeral port), write `.gs/runtime/endpoint.json`,
/// and accept agent TCP connections. `human_ui` is available via [`BusHandle::ui`].
pub fn start(runtime_root: impl AsRef<Path>) -> Result<BusHandle, Error> {
    BusHandle::start(runtime_root)
}
