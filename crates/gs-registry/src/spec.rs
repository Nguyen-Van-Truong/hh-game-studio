//! Method contract types (MASTER 4.0).

use serde::Serialize;
use std::fmt;

/// Side effect class declared on each method.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SideEffect {
    Mutating,
    ReadOnly,
    Job,
}

/// Undo class. `Special` carries a short note (MASTER 4.0 `Special("...")`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Undo {
    Auto,
    None,
    Special(&'static str),
}

/// Capability class. `Destructive` carries the cap name / note string.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Capability {
    Base,
    Destructive(&'static str),
    UiOnly,
}

/// How retries are safe.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Idempotency {
    ByCommandId,
    Natural,
    NotApplicable,
}

/// Executable method declaration. Source of truth for the bus.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct MethodSpec {
    pub name: &'static str,
    pub side_effect: SideEffect,
    pub undo: Undo,
    pub capability: Capability,
    pub idempotency: Idempotency,
    pub errors: Vec<&'static str>,
    pub emits: Vec<&'static str>,
}

impl MethodSpec {
    pub const fn is_ui_only(&self) -> bool {
        matches!(self.capability, Capability::UiOnly)
    }
}

impl fmt::Display for SideEffect {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Mutating => f.write_str("Mutating"),
            Self::ReadOnly => f.write_str("ReadOnly"),
            Self::Job => f.write_str("Job"),
        }
    }
}

impl fmt::Display for Undo {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Auto => f.write_str("Auto"),
            Self::None => f.write_str("None"),
            Self::Special(note) => write!(f, "Special({note})"),
        }
    }
}

impl fmt::Display for Capability {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Base => f.write_str("Base"),
            Self::Destructive(note) => write!(f, "Destructive({note})"),
            Self::UiOnly => f.write_str("UiOnly"),
        }
    }
}

impl fmt::Display for Idempotency {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::ByCommandId => f.write_str("ByCommandId"),
            Self::Natural => f.write_str("Natural"),
            Self::NotApplicable => f.write_str("NotApplicable"),
        }
    }
}
