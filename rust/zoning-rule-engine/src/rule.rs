//! Typed legal rules and their review state.

use std::marker::PhantomData;

use serde::{Deserialize, Serialize};

use crate::SourceSpan;

/// Stable identifier for a legal rule.
#[derive(Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(transparent)]
pub struct RuleId(pub String);

/// Whether a proposition may participate in execution.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuleStatus {
    /// Source is accounted for but not semantically interpreted.
    SourceOnly,
    /// Semantics require facts, dependencies, or legal judgment not yet modeled.
    NonExecutable,
    /// Exact source and typed semantics have been reviewed.
    Verified,
}

/// A rule whose result type is fixed at compile time.
#[derive(Clone, Debug)]
pub struct LegalRule<Result> {
    /// Stable rule identity.
    pub id: RuleId,
    /// Exact supporting source spans.
    pub sources: Vec<SourceSpan>,
    /// Review and execution state.
    pub status: RuleStatus,
    result: PhantomData<Result>,
}

impl<Result> LegalRule<Result> {
    /// Creates a typed rule declaration.
    #[must_use]
    pub fn new(id: RuleId, sources: Vec<SourceSpan>, status: RuleStatus) -> Self {
        Self {
            id,
            sources,
            status,
            result: PhantomData,
        }
    }
}
