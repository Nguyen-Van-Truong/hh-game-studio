//! Public session-panel / activity-feed types (MASTER 9.4, 9.6).

use serde::{Deserialize, Serialize};

/// Feed badge: who produced the transaction (MASTER 9.4).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Badge {
    Human,
    Agent,
    System,
}

/// One Activity Feed row — one committed transaction.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct FeedEntry {
    pub badge: Badge,
    pub actor: String,
    pub label: String,
    pub entities: Vec<String>,
    pub revision: String,
}

/// Actor row for the Session panel.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ActorInfo {
    pub actor_id: String,
    pub client_name: String,
    pub principal: String,
    pub paused: bool,
    pub command_count: u64,
    pub connected: bool,
}

/// Confirmation waiting on the human (MASTER 4.5 / 9.6).
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PendingConfirmation {
    pub confirmation_id: String,
    pub actor_id: String,
    pub method: String,
    pub summary: String,
    pub expires_in: u64,
}

/// Snapshot consumed by the Session panel.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SessionPanel {
    pub actors: Vec<ActorInfo>,
    pub pending_confirmations: Vec<PendingConfirmation>,
}

/// Server-issued principal. `human_ui` is never assigned to a TCP connection (I8 / 4.4).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Principal {
    HumanUi,
    Agent,
}

impl Principal {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::HumanUi => "human_ui",
            Self::Agent => "agent",
        }
    }

    pub fn badge(self) -> Badge {
        match self {
            Self::HumanUi => Badge::Human,
            Self::Agent => Badge::Agent,
        }
    }
}

impl Badge {
    /// Activity-feed badge text (MASTER 9.4). Human is `[BẠN]`.
    pub fn feed_label(self) -> &'static str {
        match self {
            Self::Human => "BẠN",
            Self::Agent => "AGENT",
            Self::System => "HỆ THỐNG",
        }
    }
}
