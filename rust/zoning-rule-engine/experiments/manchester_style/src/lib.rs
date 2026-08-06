//! An executable Manchester/OWL-inspired syntax experiment.
//!
//! This is deliberately not a general OWL or rule-language implementation. It
//! tests whether Manchester-style ontology declarations compose cleanly with a
//! distinct, source-faithful legal-rule module.

use std::collections::{BTreeMap, BTreeSet};

use zoning_rule_engine::{
    Bound, ConceptId, Constraint, Duration, Fact, Individual, IndividualId, Interval, Ontology,
    OntologyError, Refined, RefinementError, RelationDefinition, RelationId,
};

#[derive(Debug, Clone, Eq, PartialEq)]
pub struct ParsedOntology {
    pub name: String,
    pub concepts: BTreeSet<String>,
    pub relations: BTreeMap<String, (String, String)>,
    pub individuals: BTreeMap<String, BTreeSet<String>>,
}

#[derive(Debug, Clone, Eq, PartialEq)]
pub struct Atom {
    pub relation: String,
    pub subject: String,
    pub object: String,
}

#[derive(Debug, Clone, Eq, PartialEq)]
pub struct Provision {
    pub module: String,
    pub ontology_import: String,
    pub id: String,
    pub proposition_id: String,
    pub citation: String,
    pub source_spans: Vec<(String, String)>,
    pub status: String,
    pub exceptions: String,
    pub variables: BTreeMap<String, BTreeSet<String>>,
    pub conditions: Vec<Atom>,
    pub actor: String,
    pub action: String,
    pub object: String,
    pub minimum_days: i128,
    pub reference_event: String,
}

#[derive(Debug, Clone, Eq, PartialEq)]
pub enum CompileError {
    Syntax(String),
    UnknownVariable(String),
    UnknownRelation(String),
    TypeMismatch {
        relation: String,
        position: &'static str,
        expected: String,
        actual: String,
    },
    WrongOntologyImport {
        expected: String,
        actual: String,
    },
    Ontology(OntologyError),
}

impl From<OntologyError> for CompileError {
    fn from(value: OntologyError) -> Self {
        Self::Ontology(value)
    }
}

pub fn parse_ontology(source: &str) -> Result<ParsedOntology, CompileError> {
    let mut name = None;
    let mut concepts = BTreeSet::new();
    let mut relations = BTreeMap::new();
    let mut individuals = BTreeMap::new();
    let mut pending_relation: Option<String> = None;
    let mut pending_domain: Option<String> = None;
    let mut pending_individual: Option<String> = None;

    for raw in source.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some(value) = line.strip_prefix("Ontology:") {
            name = Some(value.trim().to_owned());
        } else if let Some(value) = line.strip_prefix("Class:") {
            concepts.insert(value.trim().to_owned());
        } else if let Some(value) = line.strip_prefix("ObjectProperty:") {
            pending_relation = Some(value.trim().to_owned());
            pending_domain = None;
            pending_individual = None;
        } else if let Some(value) = line.strip_prefix("Domain:") {
            pending_domain = Some(value.trim().to_owned());
        } else if let Some(value) = line.strip_prefix("Range:") {
            let id = pending_relation
                .take()
                .ok_or_else(|| syntax("Range without property"))?;
            let domain = pending_domain
                .take()
                .ok_or_else(|| syntax("Range without Domain"))?;
            relations.insert(id, (domain, value.trim().to_owned()));
        } else if let Some(value) = line.strip_prefix("Individual:") {
            pending_individual = Some(value.trim().to_owned());
            pending_relation = None;
        } else if let Some(value) = line.strip_prefix("Types:") {
            let id = pending_individual
                .take()
                .ok_or_else(|| syntax("Types without Individual"))?;
            individuals.insert(
                id,
                value
                    .split(',')
                    .map(|part| part.trim().to_owned())
                    .collect(),
            );
        } else {
            return Err(syntax(&format!("unrecognized ontology line: {line}")));
        }
    }
    Ok(ParsedOntology {
        name: name.ok_or_else(|| syntax("missing Ontology"))?,
        concepts,
        relations,
        individuals,
    })
}

pub fn compile_ontology(parsed: &ParsedOntology) -> Result<Ontology, CompileError> {
    let mut ontology = Ontology::new();
    for concept in &parsed.concepts {
        ontology.declare_concept(ConceptId::from(concept.as_str()));
    }
    for (id, (domain, range)) in &parsed.relations {
        ontology.declare_relation(RelationDefinition {
            id: RelationId::from(id.as_str()),
            domain: ConceptId::from(domain.as_str()),
            range: ConceptId::from(range.as_str()),
        })?;
    }
    for (id, concepts) in &parsed.individuals {
        ontology.declare_individual(Individual {
            id: IndividualId::from(id.as_str()),
            concepts: concepts
                .iter()
                .map(|x| ConceptId::from(x.as_str()))
                .collect(),
        })?;
    }
    Ok(ontology)
}

pub fn parse_rule(source: &str) -> Result<Provision, CompileError> {
    let fields: Vec<&str> = source
        .lines()
        .map(str::trim)
        .filter(|x| !x.is_empty())
        .collect();
    let one = |prefix: &str| -> Result<String, CompileError> {
        fields
            .iter()
            .find_map(|line| line.strip_prefix(prefix))
            .map(|x| x.trim().to_owned())
            .ok_or_else(|| syntax(&format!("missing {prefix}")))
    };
    let mut variables = BTreeMap::new();
    for value in fields.iter().filter_map(|line| line.strip_prefix("Given:")) {
        let (id, types) = value
            .trim()
            .split_once(' ')
            .ok_or_else(|| syntax("Given lacks type"))?;
        let types = types
            .split('&')
            .map(|part| part.trim().to_owned())
            .collect::<BTreeSet<_>>();
        if types.is_empty() || types.contains("") {
            return Err(syntax("Given contains an empty type"));
        }
        variables.insert(id.to_owned(), types);
    }
    let source_spans = fields
        .iter()
        .filter_map(|line| line.strip_prefix("SourceSpan:"))
        .map(|value| {
            let (role, quote) = value
                .split_once('|')
                .ok_or_else(|| syntax("SourceSpan needs ROLE | QUOTE"))?;
            Ok((role.trim().to_owned(), quote.trim().to_owned()))
        })
        .collect::<Result<Vec<_>, CompileError>>()?;
    if source_spans.len() != 2 {
        return Err(syntax("this fixture requires exactly two SourceSpan lines"));
    }
    let expression = one("If:")?;
    let expression = expression
        .strip_prefix('(')
        .and_then(|x| x.strip_suffix(')'))
        .ok_or_else(|| syntax("If must use explicit parentheses"))?;
    let conditions = expression
        .split("&&")
        .map(|part| parse_atom(part.trim()))
        .collect::<Result<_, _>>()?;
    let then = one("Then:")?;
    let then_parts: Vec<_> = then.split_whitespace().collect();
    if then_parts.len() != 4 || then_parts[0] != "Obligation" {
        return Err(syntax("Then must be: Obligation ACTOR ACTION OBJECT"));
    }
    let temporal = one("Temporal:")?;
    let time_parts: Vec<_> = temporal.split_whitespace().collect();
    if time_parts.len() != 7
        || time_parts[2] != ">="
        || time_parts[4] != "days"
        || time_parts[5] != "before"
    {
        return Err(syntax(
            "Temporal must be: ACTION OBJECT >= N days before EVENT",
        ));
    }
    Ok(Provision {
        module: one("RuleModule:")?,
        ontology_import: one("ImportOntology:")?,
        id: one("Provision:")?,
        proposition_id: one("PropositionId:")?,
        citation: one("Citation:")?,
        source_spans,
        status: one("Status:")?,
        exceptions: one("Exceptions:")?,
        variables,
        conditions,
        actor: then_parts[1].to_owned(),
        action: then_parts[2].to_owned(),
        object: then_parts[3].to_owned(),
        minimum_days: time_parts[3]
            .parse()
            .map_err(|_| syntax("invalid day count"))?,
        reference_event: time_parts[6].to_owned(),
    })
}

fn parse_atom(text: &str) -> Result<Atom, CompileError> {
    let (relation, arguments) = text
        .split_once('(')
        .ok_or_else(|| syntax("condition lacks ("))?;
    let arguments = arguments
        .strip_suffix(')')
        .ok_or_else(|| syntax("condition lacks )"))?;
    let (subject, object) = arguments
        .split_once(',')
        .ok_or_else(|| syntax("condition needs two arguments"))?;
    Ok(Atom {
        relation: relation.trim().to_owned(),
        subject: subject.trim().to_owned(),
        object: object.trim().to_owned(),
    })
}

pub fn typecheck(parsed: &ParsedOntology, provision: &Provision) -> Result<(), CompileError> {
    if provision.ontology_import != parsed.name {
        return Err(CompileError::WrongOntologyImport {
            expected: parsed.name.clone(),
            actual: provision.ontology_import.clone(),
        });
    }
    for atom in &provision.conditions {
        let (domain, range) = parsed
            .relations
            .get(&atom.relation)
            .ok_or_else(|| CompileError::UnknownRelation(atom.relation.clone()))?;
        check_variable(provision, &atom.subject, domain, &atom.relation, "domain")?;
        check_variable(provision, &atom.object, range, &atom.relation, "range")?;
    }
    for name in [
        &provision.actor,
        &provision.object,
        &provision.reference_event,
    ] {
        if !provision.variables.contains_key(name) {
            return Err(CompileError::UnknownVariable(name.clone()));
        }
    }
    Ok(())
}

fn check_variable(
    provision: &Provision,
    variable: &str,
    expected: &str,
    relation: &str,
    position: &'static str,
) -> Result<(), CompileError> {
    let actual = provision
        .variables
        .get(variable)
        .ok_or_else(|| CompileError::UnknownVariable(variable.to_owned()))?;
    if !actual.contains(expected) {
        return Err(CompileError::TypeMismatch {
            relation: relation.to_owned(),
            position,
            expected: expected.to_owned(),
            actual: actual.iter().cloned().collect::<Vec<_>>().join(" & "),
        });
    }
    Ok(())
}

pub fn evaluate(
    provision: &Provision,
    ontology: &Ontology,
    bindings: &BTreeMap<String, String>,
    elapsed: Duration,
) -> Option<Result<Refined<Duration, Constraint<Duration>>, RefinementError>> {
    let applicable = provision.conditions.iter().all(|atom| {
        let subject = bindings.get(&atom.subject);
        let object = bindings.get(&atom.object);
        subject.zip(object).is_some_and(|(s, o)| {
            ontology.contains(&Fact {
                subject: IndividualId::from(s.as_str()),
                relation: RelationId::from(atom.relation.as_str()),
                object: IndividualId::from(o.as_str()),
            })
        })
    });
    applicable.then(|| {
        let interval = Interval::new(
            Bound::Included(Duration::days(provision.minimum_days)),
            Bound::Unbounded,
        )
        .expect("valid parsed lower bound");
        Refined::verify(elapsed, Constraint::Interval(interval))
    })
}

fn syntax(message: &str) -> CompileError {
    CompileError::Syntax(message.to_owned())
}

#[cfg(test)]
mod tests {
    use super::*;

    const ONTOLOGY: &str = include_str!("../ontology.manchester");
    const RULE: &str = include_str!("../article_iii.rule");

    fn fixture() -> (ParsedOntology, Provision, Ontology) {
        let schema = parse_ontology(ONTOLOGY).unwrap();
        let provision = parse_rule(RULE).unwrap();
        typecheck(&schema, &provision).unwrap();
        let mut ontology = compile_ontology(&schema).unwrap();
        for (id, types) in [
            ("case:notice", ["PublishedNotice"]),
            ("case:hearing", ["PublicHearing"]),
        ] {
            ontology
                .declare_individual(Individual {
                    id: IndividualId::from(id),
                    concepts: types.into_iter().map(ConceptId::from).collect(),
                })
                .unwrap();
        }
        for (s, r, o) in [
            ("Chapter50", "requiresPublishedNotice", "case:notice"),
            ("BSEED", "responsibleFor", "case:notice"),
            ("BSEED", "forumFor", "case:hearing"),
            ("case:notice", "noticeFor", "case:hearing"),
            ("case:notice", "precedes", "case:hearing"),
        ] {
            ontology
                .assert_fact(Fact {
                    subject: IndividualId::from(s),
                    relation: RelationId::from(r),
                    object: IndividualId::from(o),
                })
                .unwrap();
        }
        (schema, provision, ontology)
    }

    #[test]
    fn exact_boundary_is_enforced() {
        let (_, rule, ontology) = fixture();
        let bindings = BTreeMap::from([
            ("regime".into(), "Chapter50".into()),
            ("agency".into(), "BSEED".into()),
            ("notice".into(), "case:notice".into()),
            ("hearing".into(), "case:hearing".into()),
        ]);
        assert!(matches!(
            evaluate(&rule, &ontology, &bindings, Duration::days(14)),
            Some(Err(_))
        ));
        assert!(matches!(
            evaluate(&rule, &ontology, &bindings, Duration::days(15)),
            Some(Ok(_))
        ));
        assert!(matches!(
            evaluate(&rule, &ontology, &bindings, Duration::days(16)),
            Some(Ok(_))
        ));
    }

    #[test]
    fn ontology_relation_types_reject_reversed_arguments() {
        let (schema, mut rule, _) = fixture();
        rule.conditions[0] = Atom {
            relation: "responsibleFor".into(),
            subject: "notice".into(),
            object: "agency".into(),
        };
        assert!(matches!(
            typecheck(&schema, &rule),
            Err(CompileError::TypeMismatch {
                position: "domain",
                ..
            })
        ));
    }

    #[test]
    fn ontology_rejects_an_invalid_fact() {
        let (_, _, mut ontology) = fixture();
        let reversed = Fact {
            subject: IndividualId::from("case:notice"),
            relation: RelationId::from("responsibleFor"),
            object: IndividualId::from("BSEED"),
        };
        assert!(matches!(
            ontology.assert_fact(reversed),
            Err(OntologyError::DomainMismatch { .. })
        ));
    }

    #[test]
    fn unrelated_ontology_extension_does_not_change_the_rule_contract() {
        let (mut schema, rule, _) = fixture();
        schema.concepts.insert("NewUnrelatedConcept".into());
        assert_eq!(typecheck(&schema, &rule), Ok(()));
    }
}
