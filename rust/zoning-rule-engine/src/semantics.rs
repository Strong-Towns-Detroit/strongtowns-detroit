//! Legal effects, powers, precedence, and unresolved interpretation.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::{RuleId, SourceSpan};

/// Assumption governing whether absence of a fact may be treated as false.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "kind")]
pub enum KnowledgePolicy {
    /// Missing facts remain unknown.
    OpenWorld,
    /// Missing facts for named predicates are false within a reviewed scope.
    ClosedWorld {
        /// Predicates covered by the closed-world declaration.
        predicates: BTreeSet<String>,
        /// Reviewed dataset or process defining completeness.
        authority: String,
    },
}

impl KnowledgePolicy {
    /// Returns whether a missing fact may be interpreted as false.
    #[must_use]
    pub fn missing_is_false(&self, predicate: &str) -> bool {
        match self {
            Self::OpenWorld => false,
            Self::ClosedWorld { predicates, .. } => predicates.contains(predicate),
        }
    }
}

/// Boolean coordination suggested by one exact source signal.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CoordinationOperator {
    /// Every coordinated expression is required.
    All,
    /// At least one coordinated expression is required.
    Any,
}

/// One source-level signal retained independently of legal interpretation.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct CoordinationSignal {
    /// Exact source fragment supporting the signal.
    pub source: SourceSpan,
    /// Operator suggested by that source fragment.
    pub suggests: CoordinationOperator,
}

/// Source signals and their separately reviewed interpretation.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct ReviewedCoordination {
    /// Potentially conflicting source-level evidence.
    pub signals: Vec<CoordinationSignal>,
    /// Resolved operator or live alternatives.
    pub interpretation: Interpretation<CoordinationOperator>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
/// The normative force of a legal conclusion.
pub enum LegalModality {
    /// An actor must perform an action.
    Obligation,
    /// An action or state is forbidden.
    Prohibition,
    /// An action is legally allowed.
    Permission,
    /// An actor has authority to alter a legal relation.
    Power,
    /// A state changes by operation of law without a discretionary act.
    AutomaticEffect,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "kind")]
/// The legal change or proposition produced by a rule.
pub enum LegalEffect {
    /// Establishes a named predicate.
    Predicate {
        /// Predicate established by the conclusion.
        predicate: String,
    },
    /// Changes one subject from one legal state to another.
    StateTransition {
        /// Subject whose legal state changes.
        subject: String,
        /// Prior state.
        from: String,
        /// Resulting state.
        to: String,
    },
    /// Confers authority on an actor.
    Authorize {
        /// Actor receiving the authority.
        actor: String,
        /// Authorized action.
        action: String,
    },
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
/// One typed conclusion of an executable legal rule.
pub struct NormativeConclusion {
    /// Normative force.
    pub modality: LegalModality,
    /// Effect carrying that force.
    pub effect: LegalEffect,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
/// An explicit ordering between two rules.
pub struct Precedence {
    /// Rule that controls in a conflict.
    pub stronger: RuleId,
    /// Rule displaced in a conflict.
    pub weaker: RuleId,
    /// Reviewed reason for the ordering.
    pub basis: PrecedenceBasis,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
/// Legal basis for one rule controlling another.
pub enum PrecedenceBasis {
    /// A source or reviewed model declares an override.
    ExplicitOverride,
    /// The source uses a notwithstanding clause.
    Notwithstanding,
    /// A reviewed specific rule controls a more general rule.
    MoreSpecific,
}

#[derive(Clone, Debug, Default)]
/// A validated acyclic graph of rule precedence.
pub struct PrecedenceGraph {
    edges: BTreeMap<RuleId, BTreeSet<RuleId>>,
}

impl PrecedenceGraph {
    /// Adds one reviewed precedence edge.
    ///
    /// # Errors
    ///
    /// Returns an error for self-precedence or a cycle.
    pub fn add(&mut self, precedence: Precedence) -> Result<(), PrecedenceError> {
        if precedence.stronger == precedence.weaker {
            return Err(PrecedenceError::SelfOverride);
        }
        if self.reaches(&precedence.weaker, &precedence.stronger) {
            return Err(PrecedenceError::Cycle);
        }
        self.edges
            .entry(precedence.stronger)
            .or_default()
            .insert(precedence.weaker);
        Ok(())
    }

    /// Tests direct or transitive precedence.
    #[must_use]
    pub fn outranks(&self, stronger: &RuleId, weaker: &RuleId) -> bool {
        self.reaches(stronger, weaker)
    }

    fn reaches(&self, start: &RuleId, target: &RuleId) -> bool {
        let mut pending = vec![start];
        let mut seen = BTreeSet::new();
        while let Some(current) = pending.pop() {
            if !seen.insert(current.clone()) {
                continue;
            }
            if let Some(next) = self.edges.get(current) {
                if next.contains(target) {
                    return true;
                }
                pending.extend(next);
            }
        }
        false
    }
}

#[derive(Clone, Copy, Debug, Error, Eq, PartialEq)]
/// Invalid precedence declaration.
pub enum PrecedenceError {
    /// A rule was declared stronger than itself.
    #[error("a rule cannot override itself")]
    SelfOverride,
    /// The new edge would create a precedence cycle.
    #[error("precedence declarations form a cycle")]
    Cycle,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "status")]
/// A reviewed semantic value or an explicitly unresolved choice.
pub enum Interpretation<T> {
    /// One interpretation has been selected through review.
    Resolved {
        /// Executable interpretation.
        value: T,
    },
    /// Competing interpretations remain live and block execution.
    Unresolved {
        /// Candidate interpretations retained for review.
        alternatives: Vec<T>,
        /// Human-readable reason resolution is required.
        reason: String,
    },
}

impl<T> Interpretation<T> {
    /// Returns a reviewed executable interpretation.
    ///
    /// # Errors
    ///
    /// Returns an error when alternatives remain unresolved.
    pub fn executable(&self) -> Result<&T, InterpretationError> {
        match self {
            Self::Resolved { value } => Ok(value),
            Self::Unresolved { .. } => Err(InterpretationError::Unresolved),
        }
    }
}

#[derive(Clone, Copy, Debug, Error, Eq, PartialEq)]
/// An interpretation is not eligible for execution.
pub enum InterpretationError {
    /// Competing alternatives have not been resolved.
    #[error("legal interpretation remains unresolved")]
    Unresolved,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn id(value: &str) -> RuleId {
        RuleId(value.to_owned())
    }

    #[test]
    fn precedence_is_transitive_and_acyclic() {
        let mut graph = PrecedenceGraph::default();
        graph
            .add(Precedence {
                stronger: id("notwithstanding"),
                weaker: id("exception"),
                basis: PrecedenceBasis::Notwithstanding,
            })
            .unwrap();
        graph
            .add(Precedence {
                stronger: id("exception"),
                weaker: id("default"),
                basis: PrecedenceBasis::ExplicitOverride,
            })
            .unwrap();
        assert!(graph.outranks(&id("notwithstanding"), &id("default")));
        assert_eq!(
            graph.add(Precedence {
                stronger: id("default"),
                weaker: id("notwithstanding"),
                basis: PrecedenceBasis::MoreSpecific
            }),
            Err(PrecedenceError::Cycle)
        );
    }

    #[test]
    fn unresolved_interpretation_cannot_execute() {
        let interpretation = Interpretation::Unresolved {
            alternatives: vec!["any_one", "all"],
            reason: "lead-in and terminal conjunction conflict".into(),
        };
        assert_eq!(
            interpretation.executable(),
            Err(InterpretationError::Unresolved)
        );
    }

    #[test]
    fn automatic_effect_is_distinct_from_a_power() {
        let lapse = NormativeConclusion {
            modality: LegalModality::AutomaticEffect,
            effect: LegalEffect::StateTransition {
                subject: "grant".into(),
                from: "effective".into(),
                to: "null_and_void".into(),
            },
        };
        let extension = NormativeConclusion {
            modality: LegalModality::Power,
            effect: LegalEffect::Authorize {
                actor: "BZA".into(),
                action: "extend_deadline".into(),
            },
        };
        assert_ne!(lapse.modality, extension.modality);
    }

    #[test]
    fn closed_world_scope_is_predicate_specific() {
        let policy = KnowledgePolicy::ClosedWorld {
            predicates: ["waiver_for".to_owned()].into(),
            authority: "complete reviewed waiver register".into(),
        };
        assert!(policy.missing_is_false("waiver_for"));
        assert!(!policy.missing_is_false("legally_established"));
        assert!(!KnowledgePolicy::OpenWorld.missing_is_false("waiver_for"));
    }
}
