//! Executable 3 x 3 matrix for the ontology and legal-rule syntax experiments.

use std::collections::{BTreeMap, BTreeSet};
use zoning_rule_engine::Duration;

const PROPOSITION_ID: &str = "detroit:article-iii:block:79:proposition:1";
const APPLICABILITY_QUOTE: &str = "Where the provisions of this chapter require that notice be published, the agency responsible for giving notice shall ensure that it is published in a newspaper of general circulation within the City. The notice shall be published:";
const DEADLINE_QUOTE: &str = "At least 15 days prior to a public hearing being held before the Buildings, Safety Engineering, and Environmental Department; or";

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Relation {
    pub id: String,
    pub domain: String,
    pub range: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CanonicalOntology {
    pub concepts: BTreeSet<String>,
    pub relations: BTreeSet<Relation>,
    pub individuals: BTreeMap<String, BTreeSet<String>>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CanonicalRule {
    pub proposition_id: String,
    pub source_quotes: Vec<String>,
    pub strict: bool,
    pub defeasible: bool,
    pub exceptions: Vec<String>,
    pub required_relations: BTreeSet<String>,
    pub minimum_days: i128,
}

impl CanonicalOntology {
    fn validate(&self, rule: &CanonicalRule) -> Result<(), String> {
        for concept in [
            "Agency",
            "HearingForum",
            "PublishedNotice",
            "PublicHearing",
            "LegalRequirement",
        ] {
            if !self.concepts.contains(concept) {
                return Err(format!("missing concept {concept}"));
            }
        }
        for relation in &rule.required_relations {
            if !self.relations.iter().any(|item| &item.id == relation) {
                return Err(format!("missing relation {relation}"));
            }
        }
        let bseed = self
            .individuals
            .get("BSEED")
            .ok_or("missing BSEED individual")?;
        if !bseed.contains("Agency") || !bseed.contains("HearingForum") {
            return Err("BSEED must be an agency and hearing forum".into());
        }
        let chapter = self
            .individuals
            .get("Chapter50")
            .ok_or("missing Chapter50 individual")?;
        if !chapter.contains("LegalRequirement") {
            return Err("Chapter50 must be a legal requirement".into());
        }
        Ok(())
    }
}

impl CanonicalRule {
    #[must_use]
    pub fn evaluate(&self, elapsed: Duration) -> bool {
        elapsed >= Duration::days(self.minimum_days)
    }

    fn validate_fixture(&self) -> Result<(), String> {
        if self.proposition_id != PROPOSITION_ID {
            return Err("wrong proposition id".into());
        }
        if self.source_quotes != [APPLICABILITY_QUOTE, DEADLINE_QUOTE] {
            return Err("reviewed source spans differ".into());
        }
        if !self.strict || self.defeasible || !self.exceptions.is_empty() {
            return Err("wrong strength or exception semantics".into());
        }
        if self.minimum_days != 15 {
            return Err("wrong inclusive temporal boundary".into());
        }
        Ok(())
    }
}

fn relation(id: &str, domain: &str, range: &str) -> Relation {
    Relation {
        id: id.into(),
        domain: domain.into(),
        range: range.into(),
    }
}

pub fn ontology_sdml() -> CanonicalOntology {
    let parsed =
        sdml_style_experiment::parse_ontology(include_str!("../../sdml_style/ontology.sdmlish"))
            .expect("valid SDML ontology");
    CanonicalOntology {
        concepts: parsed.concepts.into_iter().collect(),
        relations: parsed
            .relations
            .into_iter()
            .map(|(id, d, r)| relation(&id, &d, &r))
            .collect(),
        individuals: parsed
            .individuals
            .into_iter()
            .map(|(id, types)| (id, types.into_iter().collect()))
            .collect(),
    }
}

pub fn ontology_manchester() -> CanonicalOntology {
    let parsed = manchester_style_experiment::parse_ontology(include_str!(
        "../../manchester_style/ontology.manchester"
    ))
    .expect("valid Manchester ontology");
    let concept = |name: String| {
        if name == "LegalRegime" {
            "LegalRequirement".into()
        } else {
            name
        }
    };
    let relations = parsed
        .relations
        .into_iter()
        .map(|(id, (domain, range))| match id.as_str() {
            "responsibleFor" => relation("responsible_for", &domain, &range),
            "forumFor" => relation("forum_for", &domain, &range),
            "noticeFor" => relation("notice_for", &domain, &range),
            "requiresPublishedNotice" => relation("required_by", &concept(range), &concept(domain)),
            "precedes" => relation("precedes", &domain, &range),
            _ => relation(&id, &concept(domain), &concept(range)),
        })
        .collect();
    CanonicalOntology {
        concepts: parsed.concepts.into_iter().map(&concept).collect(),
        relations,
        individuals: parsed
            .individuals
            .into_iter()
            .map(|(id, types)| (id, types.into_iter().map(&concept).collect()))
            .collect(),
    }
}

pub fn ontology_rdf() -> CanonicalOntology {
    let parsed =
        rdf_datalog_style::parse_ontology(include_str!("../../rdf_datalog_style/ontology.zonto"))
            .expect("valid RDF ontology");
    CanonicalOntology {
        concepts: parsed.classes,
        relations: parsed
            .properties
            .into_iter()
            .map(|(id, shape)| relation(&id, &shape.domain, &shape.range))
            .collect(),
        individuals: parsed.individuals,
    }
}

fn required_relations() -> BTreeSet<String> {
    [
        "required_by",
        "responsible_for",
        "notice_for",
        "forum_for",
        "precedes",
    ]
    .into_iter()
    .map(str::to_owned)
    .collect()
}

pub fn rule_sdml() -> CanonicalRule {
    let parsed =
        sdml_style_experiment::parse_rules(include_str!("../../sdml_style/article_iii.rules"))
            .expect("valid SDML rule")
            .provision;
    CanonicalRule {
        proposition_id: parsed.id,
        source_quotes: parsed
            .sources
            .into_iter()
            .map(|source| source.quote)
            .collect(),
        strict: parsed.strict,
        defeasible: false,
        exceptions: parsed.exceptions,
        required_relations: parsed
            .conditions
            .into_iter()
            .map(|atom| atom.relation)
            .collect(),
        minimum_days: parsed.minimum_notice.as_seconds() / Duration::days(1).as_seconds(),
    }
}

pub fn rule_manchester() -> CanonicalRule {
    let parsed = manchester_style_experiment::parse_rule(include_str!(
        "../../manchester_style/article_iii.rule"
    ))
    .expect("valid Manchester rule");
    CanonicalRule {
        proposition_id: parsed.proposition_id,
        source_quotes: parsed
            .source_spans
            .into_iter()
            .map(|(_, quote)| quote)
            .collect(),
        strict: parsed.status == "Strict",
        defeasible: false,
        exceptions: if parsed.exceptions == "None" {
            Vec::new()
        } else {
            vec![parsed.exceptions]
        },
        required_relations: required_relations(),
        minimum_days: parsed.minimum_days,
    }
}

pub fn rule_datalog(ontology: &CanonicalOntology) -> CanonicalRule {
    let schema = rdf_datalog_style::OntologySchema {
        prefix: "https://detroitmi.gov/zoning/".into(),
        classes: ontology.concepts.clone(),
        properties: ontology
            .relations
            .iter()
            .map(|r| {
                (
                    r.id.clone(),
                    rdf_datalog_style::PropertyShape {
                        domain: r.domain.clone(),
                        range: r.range.clone(),
                        min_count: 1,
                    },
                )
            })
            .collect(),
        individuals: ontology.individuals.clone(),
    };
    let parsed = rdf_datalog_style::parse_rule(
        include_str!("../../rdf_datalog_style/article_iii.rules"),
        &schema,
    )
    .expect("Datalog rule parses against canonical ontology");
    CanonicalRule {
        proposition_id: parsed.proposition_id,
        source_quotes: parsed
            .sources
            .into_iter()
            .map(|source| source.quote)
            .collect(),
        strict: parsed.strict,
        defeasible: parsed.defeasible,
        exceptions: parsed.exceptions,
        required_relations: parsed
            .premises
            .into_iter()
            .filter(|atom| atom.predicate != "type" && atom.predicate != "elapsed_days")
            .map(|atom| atom.predicate)
            .collect(),
        minimum_days: parsed.minimum_elapsed_days,
    }
}

pub fn verify_pair(ontology: &CanonicalOntology, rule: &CanonicalRule) -> Result<(), String> {
    rule.validate_fixture()?;
    ontology.validate(rule)?;
    if rule.evaluate(Duration::days(14)) {
        return Err("14 days must fail".into());
    }
    if !rule.evaluate(Duration::days(15)) || !rule.evaluate(Duration::days(16)) {
        return Err("15 and 16 days must pass".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    macro_rules! cell {
        ($name:ident, $ontology:expr, $rule:expr) => {
            #[test]
            fn $name() {
                let ontology = $ontology;
                let rule = $rule(&ontology);
                verify_pair(&ontology, &rule).unwrap();
            }
        };
    }
    fn r1(_: &CanonicalOntology) -> CanonicalRule {
        rule_sdml()
    }
    fn r2(_: &CanonicalOntology) -> CanonicalRule {
        rule_manchester()
    }
    cell!(o1_r1, ontology_sdml(), r1);
    cell!(o1_r2, ontology_sdml(), r2);
    cell!(o1_r3, ontology_sdml(), rule_datalog);
    cell!(o2_r1, ontology_manchester(), r1);
    cell!(o2_r2, ontology_manchester(), r2);
    cell!(o2_r3, ontology_manchester(), rule_datalog);
    cell!(o3_r1, ontology_rdf(), r1);
    cell!(o3_r2, ontology_rdf(), r2);
    cell!(o3_r3, ontology_rdf(), rule_datalog);

    #[test]
    fn ontology_normal_forms_are_identical() {
        assert_eq!(ontology_sdml(), ontology_manchester());
        assert_eq!(ontology_sdml(), ontology_rdf());
    }
    #[test]
    fn rule_normal_forms_are_identical() {
        let o = ontology_sdml();
        assert_eq!(rule_sdml(), rule_manchester());
        assert_eq!(rule_sdml(), rule_datalog(&o));
    }
}
