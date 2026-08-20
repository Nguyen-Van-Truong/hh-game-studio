//! Immutable play-snapshot spike (WP-M-1-d / MASTER 2.4, 6.1, I3).
//!
//! Builder freezes a project fragment into `play/<play_id>/`.
//! Player stub verifies every hash and refuses a tampered snapshot.

mod builder;
mod canonical;
mod error;
mod hash;
mod manifest;
mod verify;

pub use builder::{build_snapshot, demo_request, AssetInput, BuiltSnapshot, SnapshotRequest};
pub use error::SpikeError;
pub use manifest::{AssetRecord, Manifest, SnapshotHashes, VerifiedSnapshot};
pub use verify::verify_snapshot;
