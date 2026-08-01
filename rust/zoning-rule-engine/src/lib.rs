//! Strongly typed primitives for executable land-use law.
//!
//! The crate treats JSON and RDF as projections. The canonical model is a
//! typed Rust AST in which an unqualified number or geometry cannot represent
//! a legal measurement.

pub mod aggregation;
pub mod extraction;
pub mod geometry;
pub mod language;
pub mod ontology;
pub mod provenance;
pub mod quantity;
pub mod refinement;
pub mod rule;
pub mod semantics;
pub mod temporal;

pub use aggregation::count_distinct_by_identity;
pub use extraction::{
    Candidate, CandidateDisposition, CandidateKind, CoverageReport, Extraction, LexicalHint,
    SourceDocument, TextSpan, Token, TokenKind, extract,
};
pub use geometry::{
    CoordinateReferenceSystem, DistanceTarget, Epsg2898, Epsg4326, Geometry, Polygon,
    SpatialMeasurementPolicy, SpatialPolicyId,
};
pub use language::{
    CompileError, CompiledModule, LanguageDiagnostic, ParseError, SyntaxModule, compile, diagnose,
    parse,
};
pub use ontology::{
    ConceptId, DataFact, DataPropertyDefinition, DataPropertyId, DataType, DataValue, Fact,
    Individual, IndividualId, Ontology, OntologyError, RelationDefinition, RelationId,
};
pub use provenance::{SourceSpan, SpanDigest};
pub use quantity::{Area, Duration, Length, QuantityError, Ratio, WholeCountThreshold};
pub use refinement::{Bound, Constraint, Interval, Predicate, Refined, RefinementError};
pub use rule::{LegalRule, RuleId, RuleStatus};
pub use semantics::{
    CoordinationOperator, CoordinationSignal, Interpretation, InterpretationError, KnowledgePolicy,
    LegalEffect, LegalModality, NormativeConclusion, Precedence, PrecedenceBasis, PrecedenceError,
    PrecedenceGraph, ReviewedCoordination,
};
pub use temporal::{
    CalendarOffset, CalendarPolicyId, CivilDate, LocalDateTime, LocalTime, TemporalError,
};
