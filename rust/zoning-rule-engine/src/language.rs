//! Parser and compiler for the unified zoning language.
//!
//! The authored language combines ontology declarations and legal rules in one
//! typed module graph. Controlled phrases compile to canonical n-ary
//! propositions—either structural relations or truth-valued predicates—while
//! their authored text and source location remain in the output.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::SpanDigest;

/// A parsed source module before name resolution and type checking.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SyntaxModule {
    /// Canonical module name.
    pub name: String,
    /// Concept and specialization declarations.
    pub concepts: Vec<ConceptSyntax>,
    /// Named entities and actions.
    pub individuals: Vec<IndividualSyntax>,
    /// Typed n-ary relation declarations.
    pub relations: Vec<RelationSyntax>,
    /// Typed truth-valued predicate declarations. Unlike relations, predicates
    /// may describe evidence supplied to a rule or a state derived by a rule.
    pub predicates: Vec<RelationSyntax>,
    /// Legal rule declarations.
    pub rules: Vec<RuleSyntax>,
}

/// A concept and its directly declared parent concepts.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConceptSyntax {
    /// Local concept name.
    pub name: String,
    /// Direct supertypes.
    pub parents: Vec<String>,
    /// Source line.
    pub line: usize,
}

/// Whether an individual is authored as an entity or an action.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum IndividualKind {
    /// A named legal or geographic entity.
    Entity,
    /// A named legal action with optional grammatical forms.
    Action,
}

/// A named individual in the type environment.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct IndividualSyntax {
    /// Local individual name.
    pub name: String,
    /// Declaration kind.
    pub kind: IndividualKind,
    /// Direct concept memberships.
    pub concepts: Vec<String>,
    /// Controlled-language forms such as `noun` and `gerund`.
    pub forms: BTreeMap<String, String>,
    /// Source line.
    pub line: usize,
}

/// One named and typed role in an n-ary relation.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct RelationRole {
    /// Role name used by phrase placeholders and normalized output.
    pub name: String,
    /// Required concept.
    pub concept: String,
}

/// Resolution metadata for an open-textured relation.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct InterpretiveResolution {
    /// Resolution state, initially `open`.
    pub status: String,
    /// What the controlling source does or does not define.
    pub method: String,
}

/// A typed proposition declaration and its controlled-language phrase.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RelationSyntax {
    /// Canonical local identity.
    pub name: String,
    /// Ordered, named argument roles.
    pub roles: Vec<RelationRole>,
    /// Authored phrase template.
    pub phrase: String,
    /// Present when application requires interpretation rather than derivation.
    pub interpretation: Option<InterpretiveResolution>,
    /// Source line.
    pub line: usize,
}

/// Semantic role of a declared proposition in the authored ontology.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PropositionKind {
    /// A durable structural association among independently typed things.
    Relation,
    /// A truth-valued claim that may be supplied or derived.
    Predicate,
}

/// A rule source quotation.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RuleSource {
    /// Human-readable legal citation.
    pub citation: String,
    /// Exact quoted text.
    pub quote: String,
    /// Content digest of the quote.
    pub digest: SpanDigest,
    /// Source line containing `source`.
    pub line: usize,
}

/// One universally quantified typed local binding in a `for every` block.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct BindingSyntax {
    /// Local name.
    pub name: String,
    /// Required concept.
    pub concept: String,
    /// Source line.
    pub line: usize,
}

/// An authored controlled phrase and its location.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct PhraseSyntax {
    /// Controlled-language text.
    pub text: String,
    /// Source line.
    pub line: usize,
}

/// An existentially bound medium and its typed constraints.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UsingSyntax {
    /// Local existential name.
    pub binding: BindingSyntax,
    /// Propositions the selected individual must satisfy.
    pub satisfying: Vec<PhraseSyntax>,
}

/// The first normative conclusion supported by the language.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DutySyntax {
    /// Local binding or individual bearing the duty.
    pub bearer: String,
    /// Action individual.
    pub action: String,
    /// Local binding or individual acted upon.
    pub subject: String,
    /// Controlled temporal expression.
    pub deadline: String,
    /// Optional typed means constraint.
    pub using: Option<UsingSyntax>,
}

/// An exact board-vote threshold authored without floating point or rounding.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct VoteThresholdSyntax {
    /// Decision governed by the threshold.
    pub decision: String,
    /// Named exact threshold (`majority` or `two_thirds`).
    pub threshold: VoteThresholdKind,
    /// Source line.
    pub line: usize,
}

/// Exact integer inequality selected by a vote-threshold rule.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VoteThresholdKind {
    /// `2 * concurring_votes > member_count`.
    Majority,
    /// `3 * concurring_votes >= 2 * member_count`.
    TwoThirds,
}

/// Normative or constitutive force of a phrase conclusion.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConclusionKind {
    /// Establishes a legal proposition without imposing a deontic modality.
    Constitutive,
    /// Changes legal state automatically by operation of law.
    AutomaticEffect,
    /// Forbids an action or status.
    Prohibition,
    /// Permits an action or status.
    Permission,
    /// Confers legal authority.
    Power,
}

/// A controlled phrase carrying explicit legal force.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct ConclusionSyntax {
    /// Legal force.
    pub kind: ConclusionKind,
    /// Typed phrase to establish.
    pub phrase: PhraseSyntax,
}

/// One explicitly required consequent of a rule.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", content = "value", rename_all = "snake_case")]
pub enum ConsequentSyntax {
    /// A typed duty consequent.
    Duty(DutySyntax),
    /// An exact concurrence requirement.
    VoteRequirement(VoteThresholdSyntax),
    /// A proposition carrying explicit legal force.
    Proposition(ConclusionSyntax),
}

/// The rule body as authored in an `if` block.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct RuleBodySyntax {
    /// Proposition applications that must all be established.
    pub propositions: Vec<PhraseSyntax>,
}

/// A parsed legal rule.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RuleSyntax {
    /// Local rule name.
    pub name: String,
    /// Stable rule identity.
    pub id: String,
    /// Exact supporting quotations.
    pub sources: Vec<RuleSource>,
    /// Strongly typed input parameters introduced by `given`.
    pub parameters: Vec<BindingSyntax>,
    /// Conditions under which the consequents follow.
    pub body: RuleBodySyntax,
    /// One or more explicitly required consequents.
    pub consequents: Vec<ConsequentSyntax>,
    /// Rules expressly displaced by this rule.
    pub overrides: Vec<String>,
    /// Source line.
    pub line: usize,
}

/// Whether a resolved term is a local binding or named individual.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TermKind {
    /// Universally or existentially bound local name.
    Binding,
    /// Named entity or action.
    Individual,
}

/// A typed symbol reference retained in compiled output.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ResolvedTerm {
    /// Local binding or canonical individual name.
    pub symbol: String,
    /// Inferred concept used for this application.
    pub inferred_type: String,
    /// Reference kind.
    pub kind: TermKind,
}

/// A resolved argument tied to its canonical relation role.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ResolvedArgument {
    /// Canonical role name.
    pub role: String,
    /// Required role type.
    pub required_type: String,
    /// Resolved term.
    pub term: ResolvedTerm,
}

/// A controlled phrase resolved to one canonical typed proposition.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RelationApplication {
    /// Canonical proposition identity.
    pub relation: String,
    /// Whether the resolved vocabulary item is structural or truth-valued.
    pub proposition_kind: PropositionKind,
    /// Authored controlled phrase.
    pub authored_phrase: String,
    /// Typed role assignments.
    pub arguments: Vec<ResolvedArgument>,
    /// Whether truth requires an external interpretation.
    pub interpretive: bool,
    /// Source line of this occurrence.
    pub line: usize,
}

/// Inclusive temporal lower bound before a referenced event.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompiledDeadline {
    /// Exact integral number of days.
    pub days: u64,
    /// Local event binding.
    pub before: ResolvedTerm,
    /// `true` for “at least”.
    pub inclusive: bool,
}

/// A compiled existential means constraint.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompiledUsing {
    /// Existential binding and type.
    pub binding: BindingSyntax,
    /// Typed requirements on the selected individual.
    pub satisfying: Vec<RelationApplication>,
}

/// A normalized duty conclusion.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct CompiledDuty {
    /// Duty bearer.
    pub bearer: ResolvedTerm,
    /// Required action.
    pub action: ResolvedTerm,
    /// Object of the action.
    pub subject: ResolvedTerm,
    /// Temporal constraint.
    pub deadline: CompiledDeadline,
    /// Optional typed means constraint.
    pub using: Option<CompiledUsing>,
}

/// Normalized integer inequality for a board-vote requirement.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompiledVoteThreshold {
    /// Decision governed by the requirement.
    pub decision: ResolvedTerm,
    /// Coefficient multiplying concurring votes.
    pub vote_coefficient: u64,
    /// Strict (`>`) rather than inclusive (`>=`) comparison.
    pub strict: bool,
    /// Coefficient multiplying the legally defined member count.
    pub member_coefficient: u64,
}

/// A normalized typed phrase carrying legal force.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct CompiledConclusion {
    /// Legal force preserved from source authoring.
    pub kind: ConclusionKind,
    /// Canonical typed relation application.
    pub application: RelationApplication,
}

/// One compiled, typed consequent.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", content = "value", rename_all = "snake_case")]
pub enum CompiledConsequent {
    /// A normalized duty.
    Duty(Box<CompiledDuty>),
    /// A normalized vote requirement.
    VoteRequirement(CompiledVoteThreshold),
    /// A resolved proposition carrying legal force.
    Proposition(CompiledConclusion),
}

/// A compiled rule body.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct CompiledRuleBody {
    /// Typed propositions that must all be established.
    pub propositions: Vec<RelationApplication>,
}

/// A compiled, typed legal rule.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct CompiledRule {
    /// Stable identity.
    pub id: String,
    /// Local name.
    pub name: String,
    /// Provenance.
    pub sources: Vec<RuleSource>,
    /// Typed input parameters.
    pub parameters: Vec<BindingSyntax>,
    /// Canonical proposition applications forming the body.
    pub body: CompiledRuleBody,
    /// Explicitly required typed consequents.
    pub consequents: Vec<CompiledConsequent>,
    /// Explicit precedence edges by stable rule identity.
    pub overrides: Vec<String>,
}

/// Serializable output of parsing, name resolution, phrase resolution, and
/// type checking.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompiledModule {
    /// Module identity.
    pub module: String,
    /// Parsed declarations retained for navigation.
    pub concepts: Vec<ConceptSyntax>,
    /// Parsed individuals retained for navigation.
    pub individuals: Vec<IndividualSyntax>,
    /// Parsed relations retained for navigation and rendering.
    pub relations: Vec<RelationSyntax>,
    /// Parsed predicate declarations retained for navigation and rendering.
    pub predicates: Vec<RelationSyntax>,
    /// Typed rules.
    pub rules: Vec<CompiledRule>,
    /// Canonical identities of open interpretive relations.
    pub interpretive_gaps: Vec<String>,
}

/// An authored syntax error with a source line.
#[derive(Clone, Debug, Error, Eq, PartialEq)]
#[error("line {line}: {message}")]
pub struct ParseError {
    /// One-based source line.
    pub line: usize,
    /// Diagnostic.
    pub message: String,
}

/// A name-resolution, phrase-resolution, or type-checking failure.
#[derive(Clone, Debug, Error, Eq, PartialEq)]
pub enum CompileError {
    /// A symbol is declared more than once.
    #[error("duplicate {kind} `{name}`")]
    DuplicateSymbol {
        /// Declaration kind.
        kind: &'static str,
        /// Duplicated name.
        name: String,
    },
    /// A declaration refers to an unknown concept.
    #[error("unknown concept `{0}`")]
    UnknownConcept(String),
    /// A declaration refers to an unknown local or individual.
    #[error("line {line}: unknown term `{term}`")]
    UnknownTerm {
        /// Source line.
        line: usize,
        /// Unknown name.
        term: String,
    },
    /// No controlled phrase accepts the authored text.
    #[error("line {line}: no typed relation matches `{phrase}`")]
    NoPhraseMatch {
        /// Source line.
        line: usize,
        /// Authored phrase.
        phrase: String,
    },
    /// More than one controlled phrase accepts the authored text.
    #[error("line {line}: phrase `{phrase}` is ambiguous between {relations:?}")]
    AmbiguousPhrase {
        /// Source line.
        line: usize,
        /// Authored phrase.
        phrase: String,
        /// Candidate relation identities.
        relations: Vec<String>,
    },
    /// A resolved term is outside a relation's type bound.
    #[error("line {line}: `{term}` has type `{actual}` but role `{role}` requires `{required}`")]
    TypeMismatch {
        /// Source line.
        line: usize,
        /// Term name.
        term: String,
        /// Inferred type.
        actual: String,
        /// Relation role.
        role: String,
        /// Required type.
        required: String,
    },
    /// A phrase template is malformed.
    #[error("relation `{relation}` has invalid phrase template: {message}")]
    InvalidPhraseTemplate {
        /// Relation identity.
        relation: String,
        /// Diagnostic.
        message: String,
    },
    /// A concept specialization cycle was found.
    #[error("concept specialization cycle involving `{0}`")]
    SpecializationCycle(String),
    /// A deadline is outside the implemented exact syntax.
    #[error("line {line}: unsupported deadline `{deadline}`")]
    UnsupportedDeadline {
        /// Source line.
        line: usize,
        /// Authored deadline.
        deadline: String,
    },
    /// An override names no rule in the compiled module.
    #[error("rule `{rule}` overrides unknown rule `{target}`")]
    UnknownOverride {
        /// Rule declaring precedence.
        rule: String,
        /// Missing weaker rule.
        target: String,
    },
    /// Explicit override declarations contain a cycle.
    #[error("rule override graph contains a cycle involving `{0}`")]
    OverrideCycle(String),
}

/// A stable, source-positioned diagnostic for editor and review tooling.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LanguageDiagnostic {
    /// Machine-readable diagnostic identity.
    pub code: String,
    /// One-based source line.
    pub line: usize,
    /// Human-readable explanation.
    pub message: String,
}

/// Parses and type-checks authored source, returning editor-ready diagnostics.
///
/// The compiler remains authoritative; this adapter preserves its failures in
/// a stable form that an `IntelliSense` or language-server client can consume.
#[must_use]
pub fn diagnose(source: &str) -> Vec<LanguageDiagnostic> {
    let module = match parse(source) {
        Ok(module) => module,
        Err(error) => {
            return vec![LanguageDiagnostic {
                code: "parse_error".to_owned(),
                line: error.line,
                message: error.message,
            }];
        }
    };
    match compile(&module) {
        Ok(_) => Vec::new(),
        Err(error) => vec![LanguageDiagnostic {
            code: compile_error_code(&error).to_owned(),
            line: compile_error_line(&module, &error),
            message: error.to_string(),
        }],
    }
}

fn compile_error_code(error: &CompileError) -> &'static str {
    match error {
        CompileError::UnknownConcept(_) => "unknown_concept",
        CompileError::UnknownTerm { .. } => "unknown_term",
        CompileError::NoPhraseMatch { .. } => "no_phrase_match",
        CompileError::AmbiguousPhrase { .. } => "ambiguous_phrase",
        CompileError::TypeMismatch { .. } => "type_mismatch",
        CompileError::DuplicateSymbol { .. } => "duplicate_symbol",
        CompileError::InvalidPhraseTemplate { .. } => "invalid_phrase_template",
        CompileError::SpecializationCycle(_) => "specialization_cycle",
        CompileError::UnsupportedDeadline { .. } => "unsupported_deadline",
        CompileError::UnknownOverride { .. } => "unknown_override",
        CompileError::OverrideCycle(_) => "override_cycle",
    }
}

fn compile_error_line(module: &SyntaxModule, error: &CompileError) -> usize {
    match error {
        CompileError::UnknownConcept(name) => module
            .concepts
            .iter()
            .find(|concept| concept.parents.contains(name))
            .map(|concept| concept.line)
            .or_else(|| {
                module
                    .individuals
                    .iter()
                    .find(|individual| individual.concepts.contains(name))
                    .map(|individual| individual.line)
            })
            .or_else(|| {
                module
                    .relations
                    .iter()
                    .find(|relation| relation.roles.iter().any(|role| &role.concept == name))
                    .map(|relation| relation.line)
            })
            .or_else(|| {
                module.rules.iter().find_map(|rule| {
                    rule.parameters
                        .iter()
                        .find(|binding| &binding.concept == name)
                        .map(|binding| binding.line)
                        .or_else(|| {
                            rule.consequents
                                .iter()
                                .find_map(|consequent| match consequent {
                                    ConsequentSyntax::Duty(duty) => duty.using.as_ref(),
                                    _ => None,
                                })
                                .filter(|using| &using.binding.concept == name)
                                .map(|using| using.binding.line)
                        })
                })
            })
            .unwrap_or(1),
        CompileError::UnknownTerm { line, .. }
        | CompileError::NoPhraseMatch { line, .. }
        | CompileError::AmbiguousPhrase { line, .. }
        | CompileError::TypeMismatch { line, .. }
        | CompileError::UnsupportedDeadline { line, .. } => *line,
        CompileError::InvalidPhraseTemplate { relation, .. } => module
            .relations
            .iter()
            .find(|item| &item.name == relation)
            .map_or(1, |item| item.line),
        CompileError::UnknownOverride { rule, .. } => module
            .rules
            .iter()
            .find(|item| &item.name == rule || &item.id == rule)
            .map_or(1, |item| item.line),
        CompileError::SpecializationCycle(name) => module
            .concepts
            .iter()
            .find(|item| &item.name == name)
            .map_or(1, |item| item.line),
        CompileError::DuplicateSymbol { name, .. } => module
            .concepts
            .iter()
            .filter(|item| &item.name == name)
            .nth(1)
            .map(|item| item.line)
            .or_else(|| {
                module
                    .individuals
                    .iter()
                    .filter(|item| &item.name == name)
                    .nth(1)
                    .map(|item| item.line)
            })
            .or_else(|| {
                module
                    .relations
                    .iter()
                    .filter(|item| &item.name == name)
                    .nth(1)
                    .map(|item| item.line)
            })
            .unwrap_or(1),
        CompileError::OverrideCycle(_) => 1,
    }
}

#[derive(Clone, Debug)]
struct Line {
    number: usize,
    indent: usize,
    text: String,
}

/// Parses one authored zoning-language module.
///
/// # Errors
///
/// Returns a line-addressed [`ParseError`] for malformed block structure or a
/// declaration outside the implemented grammar.
pub fn parse(source: &str) -> Result<SyntaxModule, ParseError> {
    let lines = source
        .lines()
        .enumerate()
        .filter_map(|(index, raw)| {
            let without_comment = raw.split_once('#').map_or(raw, |(head, _)| head);
            let text = without_comment.trim();
            if text.is_empty() {
                return None;
            }
            Some(Line {
                number: index + 1,
                indent: without_comment.len() - without_comment.trim_start().len(),
                text: text.to_owned(),
            })
        })
        .collect::<Vec<_>>();
    let Some(first) = lines.first() else {
        return Err(parse_error(1, "module is empty"));
    };
    let name = first
        .text
        .strip_prefix("module ")
        .ok_or_else(|| parse_error(first.number, "first declaration must be `module NAME`"))?
        .trim()
        .to_owned();
    let mut module = SyntaxModule {
        name,
        concepts: Vec::new(),
        individuals: Vec::new(),
        relations: Vec::new(),
        predicates: Vec::new(),
        rules: Vec::new(),
    };
    let mut index = 1;
    while index < lines.len() {
        let line = &lines[index];
        if line.indent != 0 {
            return Err(parse_error(line.number, "unexpected indented declaration"));
        }
        if let Some(rest) = line.text.strip_prefix("concept ") {
            let (name, parents) = parse_is_declaration(rest);
            module.concepts.push(ConceptSyntax {
                name,
                parents,
                line: line.number,
            });
            index += 1;
        } else if line.text.starts_with("entity ") || line.text.starts_with("action ") {
            let (item, next) = parse_individual(&lines, index)?;
            module.individuals.push(item);
            index = next;
        } else if line.text.starts_with("relation ")
            || line.text.starts_with("interpretive relation ")
        {
            let (relation, next) = parse_relation(&lines, index)?;
            module.relations.push(relation);
            index = next;
        } else if line.text.starts_with("predicate ")
            || line.text.starts_with("interpretive predicate ")
        {
            let (predicate, next) = parse_proposition(&lines, index, PropositionKind::Predicate)?;
            module.predicates.push(predicate);
            index = next;
        } else if line.text.starts_with("rule ") {
            let (rule, next) = parse_rule(&lines, index)?;
            module.rules.push(rule);
            index = next;
        } else {
            return Err(parse_error(
                line.number,
                format!("unsupported top-level declaration `{}`", line.text),
            ));
        }
    }
    Ok(module)
}

fn parse_individual(lines: &[Line], start: usize) -> Result<(IndividualSyntax, usize), ParseError> {
    let header = &lines[start];
    let (kind, name) = if let Some(name) = header.text.strip_prefix("entity ") {
        (IndividualKind::Entity, name.trim())
    } else {
        (
            IndividualKind::Action,
            header
                .text
                .strip_prefix("action ")
                .unwrap_or_default()
                .trim(),
        )
    };
    let end = block_end(lines, start);
    let mut concepts = Vec::new();
    let mut forms = BTreeMap::new();
    for line in &lines[start + 1..end] {
        if let Some(concept) = line.text.strip_prefix("is ") {
            concepts.push(concept.trim().to_owned());
        } else if let Some((key, value)) = parse_quoted_assignment(&line.text) {
            forms.insert(key, value);
        } else {
            return Err(parse_error(
                line.number,
                "individual entries must be `is TYPE` or `FORM \"text\"`",
            ));
        }
    }
    if concepts.is_empty() {
        return Err(parse_error(
            header.number,
            "individual requires at least one type",
        ));
    }
    Ok((
        IndividualSyntax {
            name: name.to_owned(),
            kind,
            concepts,
            forms,
            line: header.number,
        },
        end,
    ))
}

fn parse_relation(lines: &[Line], start: usize) -> Result<(RelationSyntax, usize), ParseError> {
    parse_proposition(lines, start, PropositionKind::Relation)
}

fn parse_proposition(
    lines: &[Line],
    start: usize,
    kind: PropositionKind,
) -> Result<(RelationSyntax, usize), ParseError> {
    let header = &lines[start];
    let keyword = match kind {
        PropositionKind::Relation => "relation",
        PropositionKind::Predicate => "predicate",
    };
    let interpretive_keyword = format!("interpretive {keyword} ");
    let plain_keyword = format!("{keyword} ");
    let (interpretive, name) = if let Some(name) = header.text.strip_prefix(&interpretive_keyword) {
        (true, name.trim())
    } else {
        (
            false,
            header
                .text
                .strip_prefix(&plain_keyword)
                .unwrap_or_default()
                .trim(),
        )
    };
    let end = block_end(lines, start);
    let direct_indent = header.indent + 2;
    let mut roles = Vec::new();
    let mut phrase = None;
    let mut status = None;
    let mut method = None;
    let mut index = start + 1;
    while index < end {
        let line = &lines[index];
        if line.indent != direct_indent {
            return Err(parse_error(
                line.number,
                format!("unexpected {keyword} indentation"),
            ));
        }
        if line.text == "phrase" {
            let value = lines.get(index + 1).ok_or_else(|| {
                parse_error(
                    line.number,
                    "`phrase` requires one indented quoted template",
                )
            })?;
            if value.indent <= line.indent {
                return Err(parse_error(
                    value.number,
                    "phrase template must be indented",
                ));
            }
            phrase = Some(unquote(&value.text, value.number)?);
            index += 2;
        } else if line.text == "resolution" {
            index += 1;
            while index < end && lines[index].indent > line.indent {
                let entry = &lines[index];
                let (key, value) = split_field(entry)?;
                match key.as_str() {
                    "status" => status = Some(value),
                    "method" => method = Some(value),
                    _ => return Err(parse_error(entry.number, "unknown resolution field")),
                }
                index += 1;
            }
        } else {
            let (role, concept) = split_field(line)?;
            roles.push(RelationRole {
                name: role,
                concept,
            });
            index += 1;
        }
    }
    let phrase =
        phrase.ok_or_else(|| parse_error(header.number, format!("{keyword} requires a phrase")))?;
    let interpretation = if interpretive {
        Some(InterpretiveResolution {
            status: status.ok_or_else(|| {
                parse_error(
                    header.number,
                    format!("interpretive {keyword} requires resolution status"),
                )
            })?,
            method: method.ok_or_else(|| {
                parse_error(
                    header.number,
                    format!("interpretive {keyword} requires resolution method"),
                )
            })?,
        })
    } else {
        None
    };
    Ok((
        RelationSyntax {
            name: name.to_owned(),
            roles,
            phrase,
            interpretation,
            line: header.number,
        },
        end,
    ))
}

// Each top-level rule clause is kept visible here so the parser mirrors the
// authored grammar. Clause-specific nested parsing lives in helpers.
#[allow(clippy::too_many_lines)]
fn parse_rule(lines: &[Line], start: usize) -> Result<(RuleSyntax, usize), ParseError> {
    let header = &lines[start];
    let name = header.text.strip_prefix("rule ").unwrap_or_default().trim();
    let end = block_end(lines, start);
    let direct_indent = header.indent + 2;
    let mut id = None;
    let mut sources = Vec::new();
    let mut parameters = Vec::new();
    let mut body = RuleBodySyntax {
        propositions: Vec::new(),
    };
    let mut consequents = Vec::new();
    let mut overrides = Vec::new();
    let mut index = start + 1;
    while index < end {
        let line = &lines[index];
        if line.indent != direct_indent {
            return Err(parse_error(line.number, "unexpected rule indentation"));
        }
        if let Some(value) = line.text.strip_prefix("id ") {
            id = Some(value.trim().to_owned());
            index += 1;
        } else if let Some(value) = line.text.strip_prefix("overrides ") {
            overrides.push(value.trim().to_owned());
            index += 1;
        } else if let Some(citation) = line.text.strip_prefix("source ") {
            let quote_line = lines
                .get(index + 1)
                .ok_or_else(|| parse_error(line.number, "source requires an indented quote"))?;
            if quote_line.indent <= line.indent {
                return Err(parse_error(
                    quote_line.number,
                    "source quote must be indented",
                ));
            }
            let quote = unquote(&quote_line.text, quote_line.number)?;
            sources.push(RuleSource {
                citation: citation.trim().to_owned(),
                digest: SpanDigest::of(&quote),
                quote,
                line: line.number,
            });
            index += 2;
        } else if let Some(authored) = line.text.strip_prefix("given ") {
            let (name, concept) = split_authored_field(authored, line.number)?;
            parameters.push(BindingSyntax {
                name,
                concept,
                line: line.number,
            });
            index += 1;
        } else if line.text == "given" {
            let block_stop = nested_block_end(lines, index, end);
            for entry in &lines[index + 1..block_stop] {
                if entry.indent != line.indent + 2 {
                    return Err(parse_error(entry.number, "unexpected `given` indentation"));
                }
                if !looks_like_binding(&entry.text) {
                    return Err(parse_error(
                        entry.number,
                        "`given` accepts only strongly typed `NAME: TYPE` inputs",
                    ));
                }
                let (name, concept) = split_field(entry)?;
                parameters.push(BindingSyntax {
                    name,
                    concept,
                    line: entry.number,
                });
            }
            index = block_stop;
        } else if line.text == "if" {
            index = parse_if_then(lines, index, end, &mut body, &mut consequents)?;
        } else if line.text == "for every" {
            // Rev2 compatibility. Rev3 authors use `given` for typed inputs.
            let block_stop = nested_block_end(lines, index, end);
            for entry in &lines[index + 1..block_stop] {
                if entry.indent != line.indent + 2 {
                    return Err(parse_error(
                        entry.number,
                        "unexpected `for every` indentation",
                    ));
                }
                if !looks_like_binding(&entry.text) {
                    return Err(parse_error(
                        entry.number,
                        "`for every` accepts only `NAME: TYPE` bindings",
                    ));
                }
                let (binding, concept) = split_field(entry)?;
                parameters.push(BindingSyntax {
                    name: binding,
                    concept,
                    line: entry.number,
                });
            }
            index = block_stop;
        } else if line.text == "given all" {
            // Rev 1 compatibility. Rev 2 authors should separate universal
            // bindings (`for every`) from applicability predicates (`given`).
            let block_stop = nested_block_end(lines, index, end);
            for entry in &lines[index + 1..block_stop] {
                if entry.indent != line.indent + 2 {
                    return Err(parse_error(
                        entry.number,
                        "unexpected `given all` indentation",
                    ));
                }
                if looks_like_binding(&entry.text) {
                    let (binding, concept) = split_field(entry)?;
                    parameters.push(BindingSyntax {
                        name: binding,
                        concept,
                        line: entry.number,
                    });
                } else {
                    body.propositions.push(PhraseSyntax {
                        text: entry.text.clone(),
                        line: entry.number,
                    });
                }
            }
            index = block_stop;
        } else if line.text == "require duty" {
            let (parsed, next) = parse_duty(lines, index, end)?;
            consequents.push(ConsequentSyntax::Duty(parsed));
            index = next;
        } else if line.text == "require concurrence" {
            let (parsed, next) = parse_vote_threshold(lines, index, end)?;
            consequents.push(ConsequentSyntax::VoteRequirement(parsed));
            index = next;
        } else if let Some(value) = line.text.strip_prefix("conclude ") {
            let (conclusion, next) = parse_conclusion(lines, index, value)?;
            consequents.push(ConsequentSyntax::Proposition(conclusion));
            index = next;
        } else {
            return Err(parse_error(line.number, "unsupported rule entry"));
        }
    }
    Ok((
        RuleSyntax {
            name: name.to_owned(),
            id: id.ok_or_else(|| parse_error(header.number, "rule requires an id"))?,
            sources,
            parameters,
            body,
            consequents,
            overrides,
            line: header.number,
        },
        end,
    ))
}

fn parse_vote_threshold(
    lines: &[Line],
    start: usize,
    rule_end: usize,
) -> Result<(VoteThresholdSyntax, usize), ParseError> {
    let header = &lines[start];
    let end = nested_block_end(lines, start, rule_end);
    let mut fields = BTreeMap::new();
    for entry in &lines[start + 1..end] {
        if entry.indent != header.indent + 2 {
            return Err(parse_error(
                entry.number,
                "unexpected concurrence indentation",
            ));
        }
        let (key, value) = split_field(entry)?;
        fields.insert(key, value);
    }
    let decision = fields
        .remove("decision")
        .ok_or_else(|| parse_error(header.number, "concurrence requires `decision`"))?;
    let threshold = match fields.remove("threshold").as_deref() {
        Some("majority") => VoteThresholdKind::Majority,
        Some("two_thirds") => VoteThresholdKind::TwoThirds,
        Some(_) => return Err(parse_error(header.number, "unknown vote threshold")),
        None => {
            return Err(parse_error(
                header.number,
                "concurrence requires `threshold`",
            ));
        }
    };
    if !fields.is_empty() {
        return Err(parse_error(header.number, "unsupported concurrence field"));
    }
    Ok((
        VoteThresholdSyntax {
            decision,
            threshold,
            line: header.number,
        },
        end,
    ))
}

fn parse_if_then(
    lines: &[Line],
    start: usize,
    rule_end: usize,
    body: &mut RuleBodySyntax,
    consequents: &mut Vec<ConsequentSyntax>,
) -> Result<usize, ParseError> {
    let header = &lines[start];
    let direct_indent = header.indent;
    let then_index = lines[start + 1..rule_end]
        .iter()
        .position(|line| line.indent == direct_indent && line.text == "then")
        .map(|offset| start + 1 + offset)
        .ok_or_else(|| parse_error(header.number, "`if` requires `then`"))?;
    for condition in &lines[start + 1..then_index] {
        if condition.indent != direct_indent + 2 {
            return Err(parse_error(
                condition.number,
                "unexpected conditional proposition indentation",
            ));
        }
        body.propositions.push(PhraseSyntax {
            text: condition.text.clone(),
            line: condition.number,
        });
    }
    let end_index = lines[then_index + 1..rule_end]
        .iter()
        .position(|line| line.indent == direct_indent && line.text == "end")
        .map(|offset| then_index + 1 + offset)
        .ok_or_else(|| parse_error(lines[then_index].number, "`then` requires `end`"))?;
    let mut index = then_index + 1;
    while index < end_index {
        let effect = &lines[index];
        if effect.indent != direct_indent + 2 {
            return Err(parse_error(effect.number, "unexpected `then` indentation"));
        }
        if effect.text == "require duty" {
            let (parsed, next) = parse_duty(lines, index, end_index)?;
            consequents.push(ConsequentSyntax::Duty(parsed));
            index = next;
        } else if effect.text == "require concurrence_requirement" {
            let (parsed, next) = parse_vote_threshold(lines, index, end_index)?;
            consequents.push(ConsequentSyntax::VoteRequirement(parsed));
            index = next;
        } else if let Some(value) = effect.text.strip_prefix("require ") {
            let (parsed, next) = parse_conclusion(lines, index, value)?;
            consequents.push(ConsequentSyntax::Proposition(parsed));
            index = next;
        } else {
            return Err(parse_error(effect.number, "unsupported `then` effect"));
        }
    }
    Ok(end_index + 1)
}

fn parse_conclusion(
    lines: &[Line],
    index: usize,
    value: &str,
) -> Result<(ConclusionSyntax, usize), ParseError> {
    let line = &lines[index];
    let kind = parse_conclusion_kind(value, line.number)?;
    let phrase = lines
        .get(index + 1)
        .ok_or_else(|| parse_error(line.number, "conclusion requires one indented phrase"))?;
    if phrase.indent <= line.indent {
        return Err(parse_error(
            phrase.number,
            "conclusion phrase must be indented",
        ));
    }
    Ok((
        ConclusionSyntax {
            kind,
            phrase: PhraseSyntax {
                text: phrase.text.clone(),
                line: phrase.number,
            },
        },
        index + 2,
    ))
}

fn parse_conclusion_kind(value: &str, line: usize) -> Result<ConclusionKind, ParseError> {
    match value.trim() {
        "constitutive" => Ok(ConclusionKind::Constitutive),
        "automatic_effect" => Ok(ConclusionKind::AutomaticEffect),
        "prohibition" => Ok(ConclusionKind::Prohibition),
        "permission" => Ok(ConclusionKind::Permission),
        "power" => Ok(ConclusionKind::Power),
        _ => Err(parse_error(line, "unknown conclusion kind")),
    }
}

fn parse_duty(
    lines: &[Line],
    start: usize,
    rule_end: usize,
) -> Result<(DutySyntax, usize), ParseError> {
    let header = &lines[start];
    let end = nested_block_end(lines, start, rule_end);
    let direct_indent = header.indent + 2;
    let mut fields = BTreeMap::new();
    let mut using = None;
    let mut index = start + 1;
    while index < end {
        let line = &lines[index];
        if line.indent != direct_indent {
            return Err(parse_error(line.number, "unexpected duty indentation"));
        }
        if let Some(rest) = line.text.strip_prefix("using some ") {
            let (name, concept) = rest
                .split_once(':')
                .ok_or_else(|| parse_error(line.number, "expected `using some NAME: TYPE`"))?;
            let using_end = nested_block_end(lines, index, end);
            let satisfying = lines[index + 1..using_end]
                .iter()
                .filter(|entry| entry.text != "satisfying")
                .map(|entry| PhraseSyntax {
                    text: entry.text.clone(),
                    line: entry.number,
                })
                .collect();
            using = Some(UsingSyntax {
                binding: BindingSyntax {
                    name: name.trim().to_owned(),
                    concept: concept.trim().to_owned(),
                    line: line.number,
                },
                satisfying,
            });
            index = using_end;
        } else {
            let (key, value) = split_field(line)?;
            fields.insert(key, value);
            index += 1;
        }
    }
    let take = |name: &str| {
        fields
            .get(name)
            .cloned()
            .ok_or_else(|| parse_error(header.number, format!("duty requires `{name}`")))
    };
    Ok((
        DutySyntax {
            bearer: take("bearer")?,
            action: take("action")?,
            subject: take("subject")?,
            deadline: take("deadline")?,
            using,
        },
        end,
    ))
}

fn block_end(lines: &[Line], start: usize) -> usize {
    let indent = lines[start].indent;
    lines[start + 1..]
        .iter()
        .position(|line| line.indent <= indent)
        .map_or(lines.len(), |offset| start + 1 + offset)
}

fn nested_block_end(lines: &[Line], start: usize, limit: usize) -> usize {
    let indent = lines[start].indent;
    lines[start + 1..limit]
        .iter()
        .position(|line| line.indent <= indent)
        .map_or(limit, |offset| start + 1 + offset)
}

fn parse_is_declaration(value: &str) -> (String, Vec<String>) {
    value.split_once(" is ").map_or_else(
        || (value.trim().to_owned(), Vec::new()),
        |(name, parent)| (name.trim().to_owned(), vec![parent.trim().to_owned()]),
    )
}

fn parse_quoted_assignment(value: &str) -> Option<(String, String)> {
    let (key, rest) = value.split_once(' ')?;
    if !(rest.starts_with('"') && rest.ends_with('"')) {
        return None;
    }
    Some((key.to_owned(), rest[1..rest.len() - 1].to_owned()))
}

fn unquote(value: &str, line: usize) -> Result<String, ParseError> {
    if value.starts_with('"') && value.ends_with('"') && value.len() >= 2 {
        Ok(value[1..value.len() - 1].to_owned())
    } else {
        Err(parse_error(line, "expected a quoted string"))
    }
}

fn split_field(line: &Line) -> Result<(String, String), ParseError> {
    split_authored_field(&line.text, line.number)
}

fn split_authored_field(value: &str, line: usize) -> Result<(String, String), ParseError> {
    value
        .split_once(':')
        .map(|(key, value)| (key.trim().to_owned(), value.trim().to_owned()))
        .filter(|(key, value)| !key.is_empty() && !value.is_empty())
        .ok_or_else(|| parse_error(line, "expected `NAME: VALUE`"))
}

fn looks_like_binding(value: &str) -> bool {
    value
        .split_once(':')
        .is_some_and(|(left, right)| !left.contains(' ') && !right.trim().contains(' '))
}

fn parse_error(line: usize, message: impl Into<String>) -> ParseError {
    ParseError {
        line,
        message: message.into(),
    }
}

#[derive(Clone, Debug)]
struct Environment<'a> {
    concepts: BTreeMap<&'a str, &'a ConceptSyntax>,
    individuals: BTreeMap<&'a str, &'a IndividualSyntax>,
    relations: BTreeMap<&'a str, &'a RelationSyntax>,
    predicates: BTreeMap<&'a str, &'a RelationSyntax>,
}

/// Resolves names and controlled phrases, checks relation bounds, and emits a
/// normalized representation.
///
/// # Errors
///
/// Returns [`CompileError`] for invalid specialization, unknown symbols,
/// phrase collisions, ambiguous phrases, or type mismatches.
pub fn compile(module: &SyntaxModule) -> Result<CompiledModule, CompileError> {
    let environment = build_environment(module)?;
    validate_environment(&environment)?;
    validate_overrides(module)?;
    let rules = module
        .rules
        .iter()
        .map(|rule| compile_rule(&environment, rule))
        .collect::<Result<Vec<_>, _>>()?;
    Ok(CompiledModule {
        module: module.name.clone(),
        concepts: module.concepts.clone(),
        individuals: module.individuals.clone(),
        relations: module.relations.clone(),
        predicates: module.predicates.clone(),
        rules,
        interpretive_gaps: module
            .relations
            .iter()
            .chain(&module.predicates)
            .filter(|relation| relation.interpretation.is_some())
            .map(|relation| relation.name.clone())
            .collect(),
    })
}

fn validate_overrides(module: &SyntaxModule) -> Result<(), CompileError> {
    let mut by_id = BTreeMap::new();
    for rule in &module.rules {
        if by_id.insert(rule.id.as_str(), rule).is_some() {
            return Err(CompileError::DuplicateSymbol {
                kind: "rule id",
                name: rule.id.clone(),
            });
        }
    }
    for rule in &module.rules {
        for target in &rule.overrides {
            if !by_id.contains_key(target.as_str()) {
                return Err(CompileError::UnknownOverride {
                    rule: rule.id.clone(),
                    target: target.clone(),
                });
            }
        }
    }
    let mut active = BTreeSet::new();
    let mut complete = BTreeSet::new();
    for id in by_id.keys() {
        visit_overrides(id, &by_id, &mut active, &mut complete)?;
    }
    Ok(())
}

fn visit_overrides<'a>(
    id: &'a str,
    by_id: &BTreeMap<&'a str, &'a RuleSyntax>,
    active: &mut BTreeSet<&'a str>,
    complete: &mut BTreeSet<&'a str>,
) -> Result<(), CompileError> {
    if complete.contains(id) {
        return Ok(());
    }
    if !active.insert(id) {
        return Err(CompileError::OverrideCycle(id.to_owned()));
    }
    for target in &by_id[id].overrides {
        visit_overrides(target, by_id, active, complete)?;
    }
    active.remove(id);
    complete.insert(id);
    Ok(())
}

fn build_environment(module: &SyntaxModule) -> Result<Environment<'_>, CompileError> {
    let mut concepts = BTreeMap::new();
    for concept in &module.concepts {
        if concepts.insert(concept.name.as_str(), concept).is_some() {
            return Err(CompileError::DuplicateSymbol {
                kind: "concept",
                name: concept.name.clone(),
            });
        }
    }
    let mut individuals = BTreeMap::new();
    for individual in &module.individuals {
        if individuals
            .insert(individual.name.as_str(), individual)
            .is_some()
        {
            return Err(CompileError::DuplicateSymbol {
                kind: "individual",
                name: individual.name.clone(),
            });
        }
    }
    let mut relations = BTreeMap::new();
    for relation in &module.relations {
        if relations.insert(relation.name.as_str(), relation).is_some() {
            return Err(CompileError::DuplicateSymbol {
                kind: "relation",
                name: relation.name.clone(),
            });
        }
    }
    let mut predicates = BTreeMap::new();
    for predicate in &module.predicates {
        if relations.contains_key(predicate.name.as_str())
            || predicates
                .insert(predicate.name.as_str(), predicate)
                .is_some()
        {
            return Err(CompileError::DuplicateSymbol {
                kind: "proposition",
                name: predicate.name.clone(),
            });
        }
    }
    Ok(Environment {
        concepts,
        individuals,
        relations,
        predicates,
    })
}

fn validate_environment(environment: &Environment<'_>) -> Result<(), CompileError> {
    for concept in environment.concepts.values() {
        for parent in &concept.parents {
            if !environment.concepts.contains_key(parent.as_str()) {
                return Err(CompileError::UnknownConcept(parent.clone()));
            }
            if is_subtype(environment, parent, &concept.name, &mut BTreeSet::new()) {
                return Err(CompileError::SpecializationCycle(concept.name.clone()));
            }
        }
    }
    for individual in environment.individuals.values() {
        for concept in &individual.concepts {
            if !environment.concepts.contains_key(concept.as_str()) {
                return Err(CompileError::UnknownConcept(concept.clone()));
            }
        }
    }
    let mut skeletons = BTreeMap::<String, String>::new();
    for (kind, relation) in environment
        .relations
        .values()
        .map(|item| (PropositionKind::Relation, *item))
        .chain(
            environment
                .predicates
                .values()
                .map(|item| (PropositionKind::Predicate, *item)),
        )
    {
        for role in &relation.roles {
            if !environment.concepts.contains_key(role.concept.as_str()) {
                return Err(CompileError::UnknownConcept(role.concept.clone()));
            }
        }
        validate_template(relation)?;
        let skeleton = phrase_skeleton(&relation.phrase);
        if let Some(existing) = skeletons.insert(skeleton, relation.name.clone()) {
            return Err(CompileError::InvalidPhraseTemplate {
                relation: relation.name.clone(),
                message: format!("collides with another proposition `{existing}` ({kind:?})"),
            });
        }
    }
    Ok(())
}

fn compile_rule(
    environment: &Environment<'_>,
    rule: &RuleSyntax,
) -> Result<CompiledRule, CompileError> {
    let mut bindings = BTreeMap::new();
    for parameter in &rule.parameters {
        if !environment
            .concepts
            .contains_key(parameter.concept.as_str())
        {
            return Err(CompileError::UnknownConcept(parameter.concept.clone()));
        }
        bindings.insert(parameter.name.as_str(), parameter.concept.as_str());
    }
    let propositions = rule
        .body
        .propositions
        .iter()
        .map(|phrase| resolve_phrase(environment, &bindings, phrase))
        .collect::<Result<Vec<_>, _>>()?;
    let consequents =
        rule.consequents
            .iter()
            .map(|consequent| match consequent {
                ConsequentSyntax::Duty(duty) => Ok(CompiledConsequent::Duty(Box::new(
                    compile_duty(environment, &bindings, duty, rule.line)?,
                ))),
                ConsequentSyntax::VoteRequirement(threshold) => {
                    Ok(CompiledConsequent::VoteRequirement(compile_vote_threshold(
                        environment,
                        &bindings,
                        threshold,
                    )?))
                }
                ConsequentSyntax::Proposition(conclusion) => {
                    Ok(CompiledConsequent::Proposition(CompiledConclusion {
                        kind: conclusion.kind,
                        application: resolve_phrase(environment, &bindings, &conclusion.phrase)?,
                    }))
                }
            })
            .collect::<Result<Vec<_>, CompileError>>()?;
    Ok(CompiledRule {
        id: rule.id.clone(),
        name: rule.name.clone(),
        sources: rule.sources.clone(),
        parameters: rule.parameters.clone(),
        body: CompiledRuleBody { propositions },
        consequents,
        overrides: rule.overrides.clone(),
    })
}

fn compile_duty(
    environment: &Environment<'_>,
    bindings: &BTreeMap<&str, &str>,
    duty: &DutySyntax,
    line: usize,
) -> Result<CompiledDuty, CompileError> {
    let bearer = resolve_term(environment, bindings, &duty.bearer, line)?;
    require_type(environment, &bearer, "LegalEntity", "bearer", line)?;
    let action = resolve_term(environment, bindings, &duty.action, line)?;
    require_type(environment, &action, "LegalAction", "action", line)?;
    let subject = resolve_term(environment, bindings, &duty.subject, line)?;
    require_type(environment, &subject, "LegalMatter", "subject", line)?;
    let deadline = compile_deadline(environment, bindings, &duty.deadline, line)?;
    let using = duty
        .using
        .as_ref()
        .map(|syntax| compile_using(environment, bindings, syntax))
        .transpose()?;
    Ok(CompiledDuty {
        bearer,
        action,
        subject,
        deadline,
        using,
    })
}

fn compile_using(
    environment: &Environment<'_>,
    bindings: &BTreeMap<&str, &str>,
    syntax: &UsingSyntax,
) -> Result<CompiledUsing, CompileError> {
    if !environment
        .concepts
        .contains_key(syntax.binding.concept.as_str())
    {
        return Err(CompileError::UnknownConcept(syntax.binding.concept.clone()));
    }
    let mut scoped = bindings.clone();
    scoped.insert(
        syntax.binding.name.as_str(),
        syntax.binding.concept.as_str(),
    );
    let satisfying = syntax
        .satisfying
        .iter()
        .map(|phrase| resolve_phrase(environment, &scoped, phrase))
        .collect::<Result<Vec<_>, _>>()?;
    Ok(CompiledUsing {
        binding: syntax.binding.clone(),
        satisfying,
    })
}

fn compile_vote_threshold(
    environment: &Environment<'_>,
    bindings: &BTreeMap<&str, &str>,
    threshold: &VoteThresholdSyntax,
) -> Result<CompiledVoteThreshold, CompileError> {
    let decision = resolve_term(environment, bindings, &threshold.decision, threshold.line)?;
    require_type(
        environment,
        &decision,
        "BoardDecision",
        "decision",
        threshold.line,
    )?;
    let (vote_coefficient, strict, member_coefficient) = match threshold.threshold {
        VoteThresholdKind::Majority => (2, true, 1),
        VoteThresholdKind::TwoThirds => (3, false, 2),
    };
    Ok(CompiledVoteThreshold {
        decision,
        vote_coefficient,
        strict,
        member_coefficient,
    })
}

fn compile_deadline(
    environment: &Environment<'_>,
    bindings: &BTreeMap<&str, &str>,
    value: &str,
    line: usize,
) -> Result<CompiledDeadline, CompileError> {
    let words = value.split_whitespace().collect::<Vec<_>>();
    if words.len() != 6
        || words[0] != "at"
        || words[1] != "least"
        || words[3] != "days"
        || words[4] != "before"
    {
        return Err(CompileError::UnsupportedDeadline {
            line,
            deadline: value.to_owned(),
        });
    }
    let days = words[2]
        .parse::<u64>()
        .map_err(|_| CompileError::UnsupportedDeadline {
            line,
            deadline: value.to_owned(),
        })?;
    let before = resolve_term(environment, bindings, words[5], line)?;
    require_type(environment, &before, "PublicHearing", "before", line)?;
    Ok(CompiledDeadline {
        days,
        before,
        inclusive: true,
    })
}

fn resolve_phrase(
    environment: &Environment<'_>,
    bindings: &BTreeMap<&str, &str>,
    phrase: &PhraseSyntax,
) -> Result<RelationApplication, CompileError> {
    let mut matches = Vec::new();
    for (kind, relation) in environment
        .relations
        .values()
        .map(|item| (PropositionKind::Relation, *item))
        .chain(
            environment
                .predicates
                .values()
                .map(|item| (PropositionKind::Predicate, *item)),
        )
    {
        if let Some(arguments) = match_phrase(environment, bindings, relation, phrase)? {
            matches.push((kind, relation, arguments));
        }
    }
    match matches.len() {
        0 => Err(CompileError::NoPhraseMatch {
            line: phrase.line,
            phrase: phrase.text.clone(),
        }),
        1 => {
            let (proposition_kind, relation, arguments) = matches.pop().expect("one phrase match");
            Ok(RelationApplication {
                relation: relation.name.clone(),
                proposition_kind,
                authored_phrase: phrase.text.clone(),
                arguments,
                interpretive: relation.interpretation.is_some(),
                line: phrase.line,
            })
        }
        _ => Err(CompileError::AmbiguousPhrase {
            line: phrase.line,
            phrase: phrase.text.clone(),
            relations: matches
                .into_iter()
                .map(|(_, relation, _)| relation.name.clone())
                .collect(),
        }),
    }
}

fn match_phrase(
    environment: &Environment<'_>,
    bindings: &BTreeMap<&str, &str>,
    relation: &RelationSyntax,
    phrase: &PhraseSyntax,
) -> Result<Option<Vec<ResolvedArgument>>, CompileError> {
    let template = relation.phrase.split_whitespace().collect::<Vec<_>>();
    let actual = phrase.text.split_whitespace().collect::<Vec<_>>();
    if template.len() != actual.len() {
        return Ok(None);
    }
    if template
        .iter()
        .zip(&actual)
        .any(|(expected, found)| !expected.starts_with('{') && *expected != *found)
    {
        return Ok(None);
    }
    let roles = relation
        .roles
        .iter()
        .map(|role| (role.name.as_str(), role))
        .collect::<BTreeMap<_, _>>();
    let mut arguments = Vec::new();
    for (expected, found) in template.into_iter().zip(actual) {
        let Some(placeholder) = expected
            .strip_prefix('{')
            .and_then(|value| value.strip_suffix('}'))
        else {
            if expected != found {
                return Ok(None);
            }
            continue;
        };
        let (role_name, selector) = placeholder
            .split_once(':')
            .map_or((placeholder, None), |(role, form)| (role, Some(form)));
        let role = roles
            .get(role_name)
            .ok_or_else(|| CompileError::InvalidPhraseTemplate {
                relation: relation.name.clone(),
                message: format!("unknown role `{role_name}`"),
            })?;
        let term_result = if let Some(form) = selector {
            resolve_form(environment, found, form, phrase.line)
        } else {
            resolve_term(environment, bindings, found, phrase.line)
        };
        let term = match term_result {
            Ok(term) => term,
            Err(CompileError::UnknownTerm { .. }) => return Ok(None),
            Err(error) => return Err(error),
        };
        if !term_is(environment, &term, &role.concept) {
            return Ok(None);
        }
        arguments.push(ResolvedArgument {
            role: role.name.clone(),
            required_type: role.concept.clone(),
            term,
        });
    }
    Ok(Some(arguments))
}

fn resolve_form(
    environment: &Environment<'_>,
    value: &str,
    form: &str,
    line: usize,
) -> Result<ResolvedTerm, CompileError> {
    let matches = environment
        .individuals
        .values()
        .filter(|individual| individual.forms.get(form).is_some_and(|text| text == value))
        .collect::<Vec<_>>();
    if matches.len() != 1 {
        return Err(CompileError::UnknownTerm {
            line,
            term: format!("{value} ({form} form)"),
        });
    }
    let individual = matches[0];
    Ok(ResolvedTerm {
        symbol: individual.name.clone(),
        inferred_type: individual.concepts[0].clone(),
        kind: TermKind::Individual,
    })
}

fn resolve_term(
    environment: &Environment<'_>,
    bindings: &BTreeMap<&str, &str>,
    value: &str,
    line: usize,
) -> Result<ResolvedTerm, CompileError> {
    if let Some(concept) = bindings.get(value) {
        return Ok(ResolvedTerm {
            symbol: value.to_owned(),
            inferred_type: (*concept).to_owned(),
            kind: TermKind::Binding,
        });
    }
    if let Some(individual) = environment.individuals.get(value) {
        return Ok(ResolvedTerm {
            symbol: value.to_owned(),
            inferred_type: individual.concepts[0].clone(),
            kind: TermKind::Individual,
        });
    }
    Err(CompileError::UnknownTerm {
        line,
        term: value.to_owned(),
    })
}

fn require_type(
    environment: &Environment<'_>,
    term: &ResolvedTerm,
    required: &str,
    role: &str,
    line: usize,
) -> Result<(), CompileError> {
    if term_is(environment, term, required) {
        Ok(())
    } else {
        Err(CompileError::TypeMismatch {
            line,
            term: term.symbol.clone(),
            actual: term.inferred_type.clone(),
            role: role.to_owned(),
            required: required.to_owned(),
        })
    }
}

fn term_is(environment: &Environment<'_>, term: &ResolvedTerm, required: &str) -> bool {
    if term.inferred_type == required
        || is_subtype(
            environment,
            &term.inferred_type,
            required,
            &mut BTreeSet::new(),
        )
    {
        return true;
    }
    environment
        .individuals
        .get(term.symbol.as_str())
        .is_some_and(|individual| {
            individual.concepts.iter().any(|concept| {
                concept == required
                    || is_subtype(environment, concept, required, &mut BTreeSet::new())
            })
        })
}

fn is_subtype(
    environment: &Environment<'_>,
    child: &str,
    parent: &str,
    visited: &mut BTreeSet<String>,
) -> bool {
    if child == parent {
        return true;
    }
    if !visited.insert(child.to_owned()) {
        return false;
    }
    environment.concepts.get(child).is_some_and(|concept| {
        concept
            .parents
            .iter()
            .any(|candidate| is_subtype(environment, candidate, parent, visited))
    })
}

fn validate_template(relation: &RelationSyntax) -> Result<(), CompileError> {
    let roles = relation
        .roles
        .iter()
        .map(|role| role.name.as_str())
        .collect::<BTreeSet<_>>();
    for word in relation.phrase.split_whitespace() {
        if let Some(placeholder) = word
            .strip_prefix('{')
            .and_then(|value| value.strip_suffix('}'))
        {
            let role = placeholder
                .split_once(':')
                .map_or(placeholder, |(name, _)| name);
            if !roles.contains(role) {
                return Err(CompileError::InvalidPhraseTemplate {
                    relation: relation.name.clone(),
                    message: format!("placeholder `{role}` is not a relation role"),
                });
            }
        }
    }
    Ok(())
}

fn phrase_skeleton(phrase: &str) -> String {
    phrase
        .split_whitespace()
        .map(|word| if word.starts_with('{') { "{}" } else { word })
        .collect::<Vec<_>>()
        .join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;

    const NOTICE: &str = include_str!("../examples/minimum_bseed_notice.zdl");
    const REVIEWED_RULES: &str = include_str!("../examples/reviewed_rules.zdl");

    #[test]
    fn parses_and_compiles_notice_rule() {
        let syntax = parse(NOTICE).expect("fixture parses");
        let compiled = compile(&syntax).expect("fixture compiles");
        assert_eq!(compiled.module, "detroit.article_iii.notice");
        assert_eq!(compiled.rules.len(), 1);
        assert_eq!(compiled.rules[0].body.propositions.len(), 4);
        let CompiledConsequent::Duty(duty) = &compiled.rules[0].consequents[0] else {
            panic!("notice rule must require a duty")
        };
        assert_eq!(duty.deadline.days, 15);
        assert!(duty.deadline.inclusive);
        assert_eq!(
            compiled.interpretive_gaps,
            vec!["has_general_circulation_in"]
        );
    }

    #[test]
    fn phrase_retains_canonical_relation_and_typed_roles() {
        let compiled = compile(&parse(NOTICE).unwrap()).unwrap();
        let premise = &compiled.rules[0].body.propositions[1];
        assert_eq!(premise.relation, "responsible_for");
        assert_eq!(premise.proposition_kind, PropositionKind::Predicate);
        assert_eq!(premise.arguments[0].role, "bearer");
        assert_eq!(premise.arguments[0].term.inferred_type, "PublicAgency");
        assert_eq!(premise.arguments[1].term.symbol, "publish");
        assert_eq!(premise.arguments[2].term.symbol, "hearing_notice");
    }

    #[test]
    fn interpretive_constraint_is_not_misreported_as_executable() {
        let compiled = compile(&parse(NOTICE).unwrap()).unwrap();
        let CompiledConsequent::Duty(duty) = &compiled.rules[0].consequents[0] else {
            panic!("notice rule must require a duty")
        };
        let using = duty.using.as_ref().unwrap();
        assert_eq!(using.satisfying.len(), 1);
        assert!(using.satisfying[0].interpretive);
    }

    #[test]
    fn invalid_relation_argument_is_rejected() {
        let invalid = NOTICE.replace(
            "BSEED is the forum for hearing",
            "BSEED is the forum for hearing_notice",
        );
        let error = compile(&parse(&invalid).unwrap()).unwrap_err();
        assert!(matches!(error, CompileError::NoPhraseMatch { .. }));
    }

    #[test]
    fn undeclared_entity_concept_is_rejected_and_diagnosed_at_membership() {
        let invalid = NOTICE.replace("concept Municipality is GeographicArea\n", "");
        let syntax = parse(&invalid).expect("fixture remains syntactically valid");
        assert_eq!(
            compile(&syntax),
            Err(CompileError::UnknownConcept("Municipality".to_owned()))
        );
        assert_eq!(
            diagnose(&invalid),
            vec![LanguageDiagnostic {
                code: "unknown_concept".to_owned(),
                line: 26,
                message: "unknown concept `Municipality`".to_owned(),
            }]
        );
    }

    #[test]
    fn missing_fact_is_not_encoded_as_false() {
        let compiled = compile(&parse(NOTICE).unwrap()).unwrap();
        let predicate = compiled
            .predicates
            .iter()
            .find(|predicate| predicate.name == "has_general_circulation_in")
            .unwrap();
        assert_eq!(predicate.interpretation.as_ref().unwrap().status, "open");
    }

    #[test]
    fn separates_given_parameters_from_rule_body() {
        let syntax = parse(NOTICE).unwrap();
        let rule = &syntax.rules[0];
        assert_eq!(rule.parameters.len(), 3);
        assert_eq!(rule.body.propositions.len(), 4);
        assert!(
            rule.body
                .propositions
                .iter()
                .all(|premise| !looks_like_binding(&premise.text))
        );
    }

    #[test]
    fn given_rejects_propositions() {
        let invalid = NOTICE.replace(
            "    hearing: PublicHearing",
            "    hearing: PublicHearing\n    Chapter50 requires publication of hearing_notice",
        );
        let error = parse(&invalid).unwrap_err();
        assert!(error.message.contains("accepts only strongly typed"));
    }

    #[test]
    fn inline_given_binds_one_typed_parameter() {
        let source = NOTICE.replace(
            "  given\n    agency: PublicAgency\n    hearing_notice: Notice\n    hearing: PublicHearing",
            "  given agency: PublicAgency\n  given hearing_notice: Notice\n  given hearing: PublicHearing",
        );
        let syntax = parse(&source).unwrap();
        assert_eq!(syntax.rules[0].parameters.len(), 3);
    }

    #[test]
    fn a_rule_may_require_multiple_joint_consequents() {
        let source = NOTICE.replace(
            "    require duty\n      bearer: agency",
            "    require constitutive\n      hearing_notice is notice of hearing\n    require duty\n      bearer: agency",
        );
        let compiled = compile(&parse(&source).unwrap()).unwrap();
        assert_eq!(compiled.rules[0].consequents.len(), 2);
        assert!(matches!(
            compiled.rules[0].consequents[0],
            CompiledConsequent::Proposition(_)
        ));
        assert!(matches!(
            compiled.rules[0].consequents[1],
            CompiledConsequent::Duty(_)
        ));
    }

    #[test]
    fn relation_and_predicate_names_share_one_namespace() {
        let invalid = NOTICE.replace("predicate requires_action", "relation forum_for\n  authority: LegalInstrument\n  action: LegalAction\n  subject: LegalMatter\n  phrase\n    \"{authority} requires {action:noun} of {subject}\"\n\npredicate requires_action");
        let error = compile(&parse(&invalid).unwrap()).unwrap_err();
        assert!(matches!(error, CompileError::DuplicateSymbol { .. }));
    }

    #[test]
    fn compiles_every_reviewed_statement_fixture() {
        let compiled = compile(&parse(REVIEWED_RULES).unwrap()).unwrap();
        assert_eq!(compiled.rules.len(), 15);
        assert_eq!(
            compiled
                .rules
                .iter()
                .map(|rule| rule.overrides.len())
                .sum::<usize>(),
            6
        );
        assert_eq!(compiled.interpretive_gaps.len(), 5);
        assert!(
            compiled
                .interpretive_gaps
                .contains(&"waiver_findings_satisfied".to_owned())
        );
        let CompiledConsequent::VoteRequirement(ordinary) = &compiled.rules[0].consequents[0]
        else {
            panic!("ordinary threshold must require concurrence")
        };
        assert_eq!(ordinary.vote_coefficient, 2);
        assert!(ordinary.strict);
        assert_eq!(ordinary.member_coefficient, 1);
        let CompiledConsequent::VoteRequirement(hardship) = &compiled.rules[1].consequents[0]
        else {
            panic!("hardship threshold must require concurrence")
        };
        assert_eq!(hardship.vote_coefficient, 3);
        assert!(!hardship.strict);
        assert_eq!(hardship.member_coefficient, 2);
        assert!(
            compiled
                .rules
                .iter()
                .all(|rule| !rule.consequents.is_empty())
        );
    }
}
