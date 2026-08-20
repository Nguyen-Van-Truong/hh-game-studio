use serde::{Deserialize, Serialize};

/// Play snapshot manifest — MASTER 2.4 fields plus `play_id`.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Manifest {
    pub play_id: String,
    pub document_revision: String,
    pub engine_ver: String,
    pub protocol_ver: String,
    pub seed: u64,
    pub hashes: SnapshotHashes,
    pub created_at: String,
    pub actor: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SnapshotHashes {
    pub scene: String,
    pub scripts: String,
    pub assets: String,
    pub inputmap: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AssetRecord {
    pub path: String,
    pub hash: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifiedSnapshot {
    pub play_id: String,
    pub document_revision: String,
    pub manifest: Manifest,
}
