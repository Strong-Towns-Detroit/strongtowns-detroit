//! Executable experiment: RDF/SHACL-like ontology plus Datalog-like legal rules.

use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;
use zoning_rule_engine::{Bound, Constraint, Duration, Interval, Predicate};

/// A compact schema compiled from the ontology module.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct OntologySchema {
    /// Namespace prefix.
    pub prefix: String,
    /// Declared class names.
    pub classes: BTreeSet<String>,
    /// Declared object properties.
    pub properties: BTreeMap<String, PropertyShape>,
    /// Declared individuals and their classes.
    pub individuals: BTreeMap<String, BTreeSet<String>>,
}

/// A SHACL-like object-property shape.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct PropertyShape {
    /// Required subject class.
    pub domain: String,
    /// Required object class.
    pub range: String,
    /// Minimum cardinality for conforming data.
    pub min_count: usize,
}

/// A normalized legal rule.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct CompiledRule {
    /// Rule module identifier.
    pub module: String,
    /// Imported ontology module.
    pub ontology_import: String,
    /// Stable reviewed proposition identifier.
    pub proposition_id: String,
    /// Exact reviewed source spans.
    pub sources: Vec<SourceEvidence>,
    /// Whether the proposition is interpreted as strict.
    pub strict: bool,
    /// Whether the proposition is defeasible.
    pub defeasible: bool,
    /// Explicit exception identifiers; empty means none are encoded.
    pub exceptions: Vec<String>,
    /// Variable identifying the obligated actor.
    pub obligated_actor: String,
    /// Required legal action.
    pub required_action: String,
    /// Derived predicate.
    pub head: Atom,
    /// Positive relational premises.
    pub premises: Vec<Atom>,
    /// Exact duration lower bound.
    #[serde(skip)]
    pub minimum_elapsed: Constraint<Duration>,
    /// Serializable rendering of the bound.
    pub minimum_elapsed_days: i128,
}

/// A citation paired with the exact reviewed text used to encode the rule.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct SourceEvidence {
    /// Ordinance locator.
    pub citation: String,
    /// Exact reviewed quotation.
    pub quote: String,
}

/// A normalized predicate application.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Atom {
    /// Predicate name.
    pub predicate: String,
    /// Arguments, which may be variables or ontology terms.
    pub arguments: Vec<String>,
}

/// A tiny fact graph used to validate schema and evaluate the example rule.
#[derive(Debug, Clone, Default)]
pub struct FactGraph {
    types: BTreeMap<String, BTreeSet<String>>,
    relations: BTreeSet<(String, String, String)>,
}

/// Parsing, validation, or evaluation failure.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum ExperimentError {
    /// Source line is outside this experiment's grammar.
    #[error("invalid syntax: {0}")]
    Syntax(String),
    /// A referenced class was not declared.
    #[error("unknown class: {0}")]
    UnknownClass(String),
    /// A referenced property was not declared.
    #[error("unknown property: {0}")]
    UnknownProperty(String),
    /// A fact violates the property's declared domain or range.
    #[error("{property} expects {expected} at {position}, but {individual} is not typed as it")]
    ShapeViolation {
        /// Property being asserted.
        property: String,
        /// `domain` or `range`.
        position: &'static str,
        /// Expected class.
        expected: String,
        /// Nonconforming individual.
        individual: String,
    },
}

/// Parse the experiment's RDF/SHACL-inspired ontology syntax.
pub fn parse_ontology(source: &str) -> Result<OntologySchema, ExperimentError> {
    let mut schema = OntologySchema {
        prefix: String::new(),
        classes: BTreeSet::new(),
        properties: BTreeMap::new(),
        individuals: BTreeMap::new(),
    };
    for raw in source.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let words: Vec<_> = line.split_whitespace().collect();
        match words.as_slice() {
            ["prefix", _name, iri] => schema.prefix = (*iri).to_owned(),
            ["class", name] => {
                schema.classes.insert((*name).to_owned());
            }
            [
                "property",
                name,
                "domain",
                domain,
                "range",
                range,
                "min",
                count,
            ] => {
                let min_count = count
                    .parse()
                    .map_err(|_| ExperimentError::Syntax(line.to_owned()))?;
                schema.properties.insert(
                    (*name).to_owned(),
                    PropertyShape {
                        domain: (*domain).to_owned(),
                        range: (*range).to_owned(),
                        min_count,
                    },
                );
            }
            ["individual", name, "types", types] => {
                schema.individuals.insert(
                    (*name).to_owned(),
                    types.split(',').map(str::to_owned).collect(),
                );
            }
            _ => return Err(ExperimentError::Syntax(line.to_owned())),
        }
    }
    for shape in schema.properties.values() {
        for class in [&shape.domain, &shape.range] {
            if !schema.classes.contains(class) {
                return Err(ExperimentError::UnknownClass(class.clone()));
            }
        }
    }
    for types in schema.individuals.values() {
        for class in types {
            if !schema.classes.contains(class) {
                return Err(ExperimentError::UnknownClass(class.clone()));
            }
        }
    }
    Ok(schema)
}

/// Parse the deliberately narrow Datalog rule used by this vertical slice.
pub fn parse_rule(source: &str, schema: &OntologySchema) -> Result<CompiledRule, ExperimentError> {
    let significant: Vec<_> = source
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .collect();
    let module = significant
        .first()
        .and_then(|line| line.strip_prefix("module "))
        .ok_or_else(|| ExperimentError::Syntax("missing module".to_owned()))?
        .to_owned();
    let ontology_import = significant
        .get(1)
        .and_then(|line| line.strip_prefix("import "))
        .ok_or_else(|| ExperimentError::Syntax("missing import".to_owned()))?
        .to_owned();
    let proposition_id = significant
        .get(2)
        .and_then(|line| line.strip_prefix("id "))
        .ok_or_else(|| ExperimentError::Syntax("missing proposition id".to_owned()))?
        .to_owned();
    let mut cursor = 3;
    let mut sources = Vec::new();
    while let Some(span) = significant
        .get(cursor)
        .and_then(|line| line.strip_prefix("source-span "))
    {
        let (citation, quote) = span
            .split_once(" | ")
            .ok_or_else(|| ExperimentError::Syntax(span.to_owned()))?;
        sources.push(SourceEvidence {
            citation: citation.to_owned(),
            quote: quote.to_owned(),
        });
        cursor += 1;
    }
    if sources.len() != 2 {
        return Err(ExperimentError::Syntax(
            "exactly two reviewed source spans required".to_owned(),
        ));
    }
    let strict = significant.get(cursor) == Some(&"strength strict");
    if !strict {
        return Err(ExperimentError::Syntax(
            "strength must be explicit".to_owned(),
        ));
    }
    cursor += 1;
    let defeasible = match significant.get(cursor).copied() {
        Some("defeasible false") => false,
        Some("defeasible true") => true,
        _ => return Err(ExperimentError::Syntax("defeasibility required".to_owned())),
    };
    cursor += 1;
    let exception_text = significant
        .get(cursor)
        .and_then(|line| line.strip_prefix("exceptions "))
        .ok_or_else(|| ExperimentError::Syntax("exceptions required".to_owned()))?;
    let exceptions = if exception_text == "none" {
        Vec::new()
    } else {
        exception_text.split(',').map(str::to_owned).collect()
    };
    cursor += 1;
    let obligation = significant
        .get(cursor)
        .and_then(|line| line.strip_prefix("obligation actor "))
        .ok_or_else(|| ExperimentError::Syntax("missing obligation".to_owned()))?;
    let (obligated_actor, required_action) = obligation
        .split_once(" action ")
        .ok_or_else(|| ExperimentError::Syntax(obligation.to_owned()))?;
    cursor += 1;
    let body = significant[cursor..].join(" ");
    let (head_text, premises_text) = body
        .split_once(":-")
        .ok_or_else(|| ExperimentError::Syntax("missing :-".to_owned()))?;
    let head = parse_atom(head_text.trim())?;
    let premise_text = premises_text.trim().trim_end_matches('.');
    let pieces = split_atoms(premise_text);
    let mut premises = Vec::new();
    let mut minimum_days = None;
    for piece in pieces {
        if let Some(value) = piece.strip_prefix("Days >= ") {
            minimum_days = Some(
                value
                    .parse::<i128>()
                    .map_err(|_| ExperimentError::Syntax(piece.to_owned()))?,
            );
        } else {
            premises.push(parse_atom(piece)?);
        }
    }
    for atom in &premises {
        if atom.predicate == "type" {
            let class = atom
                .arguments
                .get(1)
                .ok_or_else(|| ExperimentError::Syntax("type requires two arguments".to_owned()))?;
            if !schema.classes.contains(class) {
                return Err(ExperimentError::UnknownClass(class.clone()));
            }
            continue;
        }
        if atom.predicate == "elapsed_days" {
            continue;
        }
        if !schema.properties.contains_key(&atom.predicate) {
            return Err(ExperimentError::UnknownProperty(atom.predicate.clone()));
        }
    }
    let minimum_elapsed_days = minimum_days
        .ok_or_else(|| ExperimentError::Syntax("missing duration comparison".to_owned()))?;
    let minimum_elapsed = Constraint::Interval(
        Interval::new(
            Bound::Included(Duration::days(minimum_elapsed_days)),
            Bound::Unbounded,
        )
        .map_err(|error| ExperimentError::Syntax(error.to_string()))?,
    );
    Ok(CompiledRule {
        module,
        ontology_import,
        proposition_id,
        sources,
        strict,
        defeasible,
        exceptions,
        obligated_actor: obligated_actor.to_owned(),
        required_action: required_action.to_owned(),
        head,
        premises,
        minimum_elapsed,
        minimum_elapsed_days,
    })
}

fn split_atoms(source: &str) -> Vec<&str> {
    let mut depth = 0_u32;
    let mut start = 0;
    let mut result = Vec::new();
    for (index, character) in source.char_indices() {
        match character {
            '(' => depth += 1,
            ')' => depth -= 1,
            ',' if depth == 0 => {
                result.push(source[start..index].trim());
                start = index + 1;
            }
            _ => {}
        }
    }
    result.push(source[start..].trim());
    result
}

fn parse_atom(source: &str) -> Result<Atom, ExperimentError> {
    let (predicate, rest) = source
        .split_once('(')
        .ok_or_else(|| ExperimentError::Syntax(source.to_owned()))?;
    let arguments = rest
        .trim_end_matches(')')
        .split(',')
        .map(|argument| argument.trim().to_owned())
        .collect();
    Ok(Atom {
        predicate: predicate.trim().to_owned(),
        arguments,
    })
}

impl FactGraph {
    /// Seed the graph with ontology individuals.
    #[must_use]
    pub fn from_schema(schema: &OntologySchema) -> Self {
        Self {
            types: schema.individuals.clone(),
            relations: BTreeSet::new(),
        }
    }

    /// Assert that an individual is an instance of a declared class.
    pub fn add_type(
        &mut self,
        schema: &OntologySchema,
        individual: &str,
        class: &str,
    ) -> Result<(), ExperimentError> {
        if !schema.classes.contains(class) {
            return Err(ExperimentError::UnknownClass(class.to_owned()));
        }
        self.types
            .entry(individual.to_owned())
            .or_default()
            .insert(class.to_owned());
        Ok(())
    }

    /// Assert a relation after checking its SHACL-like domain and range.
    pub fn add_relation(
        &mut self,
        schema: &OntologySchema,
        property: &str,
        subject: &str,
        object: &str,
    ) -> Result<(), ExperimentError> {
        let shape = schema
            .properties
            .get(property)
            .ok_or_else(|| ExperimentError::UnknownProperty(property.to_owned()))?;
        self.require_type(property, "domain", subject, &shape.domain)?;
        self.require_type(property, "range", object, &shape.range)?;
        self.relations
            .insert((property.to_owned(), subject.to_owned(), object.to_owned()));
        Ok(())
    }

    fn require_type(
        &self,
        property: &str,
        position: &'static str,
        individual: &str,
        expected: &str,
    ) -> Result<(), ExperimentError> {
        if self
            .types
            .get(individual)
            .is_some_and(|types| types.contains(expected))
        {
            Ok(())
        } else {
            Err(ExperimentError::ShapeViolation {
                property: property.to_owned(),
                position,
                expected: expected.to_owned(),
                individual: individual.to_owned(),
            })
        }
    }

    /// Evaluate the example rule for already-linked notice and hearing facts.
    ///
    /// Missing premises return `false`; this is a local closed-world evaluation
    /// policy, not an assertion that the missing RDF facts are false.
    #[must_use]
    pub fn evaluates_notice_rule(
        &self,
        rule: &CompiledRule,
        agency: &str,
        notice: &str,
        hearing: &str,
        elapsed: Duration,
    ) -> bool {
        let typed = |individual: &str, class: &str| {
            self.types
                .get(individual)
                .is_some_and(|types| types.contains(class))
        };
        typed(notice, "PublishedNotice")
            && typed(hearing, "PublicHearing")
            && typed(agency, "Agency")
            && typed("Chapter50", "LegalRequirement")
            && self.relations.contains(&(
                "required_by".to_owned(),
                notice.to_owned(),
                "Chapter50".to_owned(),
            ))
            && self.relations.contains(&(
                "responsible_for".to_owned(),
                agency.to_owned(),
                notice.to_owned(),
            ))
            && self.relations.contains(&(
                "notice_for".to_owned(),
                notice.to_owned(),
                hearing.to_owned(),
            ))
            && self.relations.contains(&(
                "forum_for".to_owned(),
                "BSEED".to_owned(),
                hearing.to_owned(),
            ))
            && self.relations.contains(&(
                "precedes".to_owned(),
                notice.to_owned(),
                hearing.to_owned(),
            ))
            && rule.minimum_elapsed.test(&elapsed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> (OntologySchema, CompiledRule, FactGraph) {
        let schema = parse_ontology(include_str!("../ontology.zonto")).unwrap();
        let rule = parse_rule(include_str!("../article_iii.rules"), &schema).unwrap();
        let mut graph = FactGraph::from_schema(&schema);
        graph
            .add_type(&schema, "notice-1", "PublishedNotice")
            .unwrap();
        graph
            .add_type(&schema, "hearing-1", "PublicHearing")
            .unwrap();
        graph
            .add_type(&schema, "responsible-agency", "Agency")
            .unwrap();
        graph
            .add_relation(&schema, "notice_for", "notice-1", "hearing-1")
            .unwrap();
        graph
            .add_relation(&schema, "required_by", "notice-1", "Chapter50")
            .unwrap();
        graph
            .add_relation(&schema, "responsible_for", "responsible-agency", "notice-1")
            .unwrap();
        graph
            .add_relation(&schema, "forum_for", "BSEED", "hearing-1")
            .unwrap();
        graph
            .add_relation(&schema, "precedes", "notice-1", "hearing-1")
            .unwrap();
        (schema, rule, graph)
    }

    #[test]
    fn exact_boundary_is_inclusive() {
        let (_, rule, graph) = fixture();
        assert!(!graph.evaluates_notice_rule(
            &rule,
            "responsible-agency",
            "notice-1",
            "hearing-1",
            Duration::days(14)
        ));
        assert!(graph.evaluates_notice_rule(
            &rule,
            "responsible-agency",
            "notice-1",
            "hearing-1",
            Duration::days(15)
        ));
        assert!(graph.evaluates_notice_rule(
            &rule,
            "responsible-agency",
            "notice-1",
            "hearing-1",
            Duration::days(16)
        ));
    }

    #[test]
    fn source_and_legal_metadata_survive_normalization() {
        let (_, rule, _) = fixture();
        assert_eq!(
            rule.proposition_id,
            "detroit:article-iii:block:79:proposition:1"
        );
        assert_eq!(rule.sources.len(), 2);
        assert!(rule.sources[0].quote.starts_with("Where the provisions"));
        assert!(rule.sources[1].quote.starts_with("At least 15 days"));
        assert!(rule.strict);
        assert!(!rule.defeasible);
        assert!(rule.exceptions.is_empty());
        assert_eq!(rule.obligated_actor, "Agency");
        assert_eq!(rule.required_action, "publish_notice");
    }

    #[test]
    fn shape_validation_rejects_reversed_fact() {
        let (schema, _, mut graph) = fixture();
        let error = graph
            .add_relation(&schema, "notice_for", "hearing-1", "notice-1")
            .unwrap_err();
        assert_eq!(
            error,
            ExperimentError::ShapeViolation {
                property: "notice_for".to_owned(),
                position: "domain",
                expected: "PublishedNotice".to_owned(),
                individual: "hearing-1".to_owned(),
            }
        );
    }

    #[test]
    fn rule_is_bound_to_declared_ontology_properties() {
        let schema = parse_ontology(include_str!("../ontology.zonto")).unwrap();
        let invalid = include_str!("../article_iii.rules").replace("notice_for", "mystery_for");
        assert_eq!(
            parse_rule(&invalid, &schema).unwrap_err(),
            ExperimentError::UnknownProperty("mystery_for".to_owned())
        );
    }
}
