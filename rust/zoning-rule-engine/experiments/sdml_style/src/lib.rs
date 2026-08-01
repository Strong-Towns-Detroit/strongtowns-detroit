//! Executable SDML-inspired syntax experiment. This intentionally implements
//! only enough grammar for one vertical slice; it is not an SDML parser.

use std::collections::{BTreeMap, BTreeSet};

use zoning_rule_engine::{
    ConceptId, Duration, Fact, Individual, IndividualId, Ontology, OntologyError,
    RelationDefinition, RelationId,
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OntologyModule {
    pub name: String,
    pub concepts: Vec<String>,
    pub individuals: Vec<(String, Vec<String>)>,
    pub relations: Vec<(String, String, String)>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuleModule {
    pub name: String,
    pub import: String,
    pub provision: Provision,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Provision {
    pub id: String,
    pub name: String,
    pub sources: Vec<SourceReference>,
    pub strict: bool,
    pub exceptions: Vec<String>,
    pub variables: BTreeMap<String, String>,
    pub conditions: Vec<Atom>,
    pub minimum_notice: Duration,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SourceReference {
    pub citation: String,
    pub quote: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Atom {
    pub relation: String,
    pub subject: String,
    pub object: String,
}

pub fn parse_ontology(source: &str) -> Result<OntologyModule, String> {
    let lines: Vec<_> = source
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .collect();
    let name = lines[0]
        .strip_prefix("module ")
        .and_then(|x| x.strip_suffix(" is"))
        .ok_or("ontology must start with `module NAME is`")?
        .to_owned();
    let mut concepts = Vec::new();
    let mut individuals = Vec::new();
    let mut relations = Vec::new();
    let mut index = 1;
    while index < lines.len() {
        let line = lines[index];
        if let Some(value) = line.strip_prefix("concept ") {
            concepts.push(value.to_owned());
        } else if let Some(value) = line.strip_prefix("individual ") {
            let (id, types) = value
                .split_once(" is ")
                .ok_or("invalid individual declaration")?;
            individuals.push((
                id.to_owned(),
                types.split(',').map(|x| x.trim().to_owned()).collect(),
            ));
        } else if let Some(id) = line
            .strip_prefix("relation ")
            .and_then(|x| x.strip_suffix(" is"))
        {
            let domain = lines
                .get(index + 1)
                .and_then(|x| x.strip_prefix("from "))
                .ok_or("relation missing from")?;
            let range = lines
                .get(index + 2)
                .and_then(|x| x.strip_prefix("to "))
                .ok_or("relation missing to")?;
            if lines.get(index + 3) != Some(&"end") {
                return Err("relation missing end".into());
            }
            relations.push((id.to_owned(), domain.to_owned(), range.to_owned()));
            index += 3;
        }
        index += 1;
    }
    Ok(OntologyModule {
        name,
        concepts,
        individuals,
        relations,
    })
}

pub fn compile_ontology(module: &OntologyModule) -> Result<Ontology, OntologyError> {
    let mut ontology = Ontology::new();
    for concept in &module.concepts {
        ontology.declare_concept(ConceptId(concept.clone()));
    }
    for (id, types) in &module.individuals {
        ontology.declare_individual(Individual {
            id: IndividualId(id.clone()),
            concepts: types
                .iter()
                .cloned()
                .map(ConceptId)
                .collect::<BTreeSet<_>>(),
        })?;
    }
    for (id, domain, range) in &module.relations {
        ontology.declare_relation(RelationDefinition {
            id: RelationId(id.clone()),
            domain: ConceptId(domain.clone()),
            range: ConceptId(range.clone()),
        })?;
    }
    Ok(ontology)
}

pub fn parse_rules(source: &str) -> Result<RuleModule, String> {
    let lines: Vec<_> = source
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .collect();
    let name = lines[0]
        .strip_prefix("module ")
        .ok_or("rule module name missing")?
        .to_owned();
    let import = lines[1]
        .strip_prefix("import ")
        .ok_or("rule import missing")?
        .to_owned();
    let provision_name = lines[2]
        .strip_prefix("provision ")
        .ok_or("provision missing")?
        .to_owned();
    let mut id = None;
    let mut sources = Vec::new();
    let mut strict = false;
    let mut variables = BTreeMap::new();
    let mut conditions = Vec::new();
    let mut minimum_notice = None;
    for line in &lines[3..] {
        if let Some(value) = line.strip_prefix("id ") {
            id = Some(value.trim_matches('"').to_owned());
        }
        if let Some(value) = line.strip_prefix("source ") {
            let (citation, quote) = value.split_once(" quote ").ok_or("source quote missing")?;
            sources.push(SourceReference {
                citation: citation.trim_matches('"').to_owned(),
                quote: quote.trim_matches('"').to_owned(),
            });
        }
        if *line == "strength strict" {
            strict = true;
        }
        if let Some(value) = line.strip_prefix("given ") {
            let (id, ty) = value.split_once(':').ok_or("invalid given")?;
            variables.insert(id.trim().to_owned(), ty.trim().to_owned());
        }
        if let Some(expression) = line.strip_prefix("if ") {
            for raw in expression.split(" && ") {
                let (relation, args) = raw.split_once('(').ok_or("invalid atom")?;
                let args = args.strip_suffix(')').ok_or("invalid atom close")?;
                let (subject, object) = args.split_once(',').ok_or("binary atom required")?;
                conditions.push(Atom {
                    relation: relation.into(),
                    subject: subject.trim().into(),
                    object: object.trim().into(),
                });
            }
        }
        if let Some(expression) = line.strip_prefix("then ") {
            let days = expression
                .split(">=")
                .nth(1)
                .and_then(|x| x.trim().strip_suffix(" days"))
                .ok_or("unsupported consequence")?
                .parse::<i128>()
                .map_err(|_| "invalid days")?;
            minimum_notice = Some(Duration::days(days));
        }
    }
    Ok(RuleModule {
        name,
        import,
        provision: Provision {
            id: id.ok_or("stable proposition id missing")?,
            name: provision_name,
            sources,
            strict,
            exceptions: Vec::new(),
            variables,
            conditions,
            minimum_notice: minimum_notice.ok_or("consequence missing")?,
        },
    })
}

pub fn validate_rule(module: &RuleModule, ontology_module: &OntologyModule) -> Result<(), String> {
    if module.import != ontology_module.name {
        return Err("unresolved ontology import".into());
    }
    let relations: BTreeMap<_, _> = ontology_module
        .relations
        .iter()
        .map(|(id, domain, range)| (id.as_str(), (domain.as_str(), range.as_str())))
        .collect();
    let individuals: BTreeMap<_, _> = ontology_module
        .individuals
        .iter()
        .map(|(id, types)| (id.as_str(), types))
        .collect();
    for atom in &module.provision.conditions {
        let (domain, range) = relations
            .get(atom.relation.as_str())
            .ok_or("unknown relation")?;
        validate_term(
            &atom.subject,
            domain,
            &module.provision.variables,
            &individuals,
        )?;
        validate_term(
            &atom.object,
            range,
            &module.provision.variables,
            &individuals,
        )?;
    }
    Ok(())
}

fn validate_term(
    term: &str,
    expected: &str,
    variables: &BTreeMap<String, String>,
    individuals: &BTreeMap<&str, &Vec<String>>,
) -> Result<(), String> {
    if let Some(actual) = variables.get(term) {
        if actual == expected {
            Ok(())
        } else {
            Err(format!(
                "type mismatch: {term} is {actual}, expected {expected}"
            ))
        }
    } else if let Some(types) = individuals.get(term) {
        if types.iter().any(|ty| ty == expected) {
            Ok(())
        } else {
            Err(format!(
                "domain/range mismatch for {term}: expected {expected}"
            ))
        }
    } else {
        Err(format!("unknown term: {term}"))
    }
}

pub fn assert_case_fact(
    ontology: &mut Ontology,
    relation: &str,
    subject: &str,
    object: &str,
) -> Result<(), OntologyError> {
    ontology.assert_fact(Fact {
        subject: IndividualId(subject.into()),
        relation: RelationId(relation.into()),
        object: IndividualId(object.into()),
    })
}

pub fn notice_satisfies(provision: &Provision, elapsed: Duration) -> bool {
    elapsed >= provision.minimum_notice
}

#[cfg(test)]
mod tests {
    use super::*;

    const ONTOLOGY: &str = include_str!("../ontology.sdmlish");
    const RULES: &str = include_str!("../article_iii.rules");

    #[test]
    fn exact_boundary_is_inclusive() {
        let ontology = parse_ontology(ONTOLOGY).unwrap();
        let rules = parse_rules(RULES).unwrap();
        validate_rule(&rules, &ontology).unwrap();
        assert!(!notice_satisfies(&rules.provision, Duration::days(14)));
        assert!(notice_satisfies(&rules.provision, Duration::days(15)));
        assert!(notice_satisfies(&rules.provision, Duration::days(16)));
        assert_eq!(rules.provision.sources.len(), 2);
        assert!(rules.provision.strict);
        assert!(rules.provision.exceptions.is_empty());
    }

    #[test]
    fn compiler_rejects_domain_range_mismatch() {
        let ontology = parse_ontology(ONTOLOGY).unwrap();
        let mut rules = parse_rules(RULES).unwrap();
        rules.provision.conditions[0].subject = "agency".into();
        assert!(validate_rule(&rules, &ontology)
            .unwrap_err()
            .contains("type mismatch"));
    }

    #[test]
    fn runtime_ontology_rejects_reversed_fact() {
        let module = parse_ontology(ONTOLOGY).unwrap();
        let mut ontology = compile_ontology(&module).unwrap();
        ontology
            .declare_individual(Individual {
                id: IndividualId("notice-1".into()),
                concepts: [ConceptId("PublishedNotice".into())].into(),
            })
            .unwrap();
        let error =
            assert_case_fact(&mut ontology, "responsible_for", "notice-1", "BSEED").unwrap_err();
        assert!(matches!(error, OntologyError::DomainMismatch { .. }));
    }

    #[test]
    fn modules_change_independently_until_import_contract_breaks() {
        let ontology = parse_ontology(&ONTOLOGY.replace(
            "concept LegalRequirement",
            "concept LegalRequirement\n  concept Newspaper",
        ))
        .unwrap();
        let rules = parse_rules(RULES).unwrap();
        validate_rule(&rules, &ontology).unwrap();

        let renamed = parse_ontology(
            &ONTOLOGY.replace("module detroit_hearings is", "module renamed_hearings is"),
        )
        .unwrap();
        assert_eq!(
            validate_rule(&rules, &renamed).unwrap_err(),
            "unresolved ontology import"
        );
    }
}
