//! Executable spike for Detroit Zoning Ordinance § 50-3-10.
//!
//! Run with:
//! `cargo run --example article_iii_notice`

use std::collections::BTreeSet;

use zoning_rule_engine::{
    Bound, ConceptId, Constraint, Duration, Fact, Individual, IndividualId, Interval, LegalRule,
    Ontology, Refined, RefinementError, RelationDefinition, RelationId, RuleId, RuleStatus,
    SourceSpan,
};

type NoticePeriod = Refined<Duration, Constraint<Duration>>;

const SNAPSHOT: &str = "2025-10-09_job-429936";
const DOCUMENT: &str = "ARTICLE_III.municode.json";
const NODE: &str = "COCH50_CH50ZO_ARTIIIREAPPRPA1_DIV1GEPR_S50-3-10NOPUNENO";

const APPLICABILITY_SOURCE: &str = "Where the provisions of this chapter require that notice be published, the agency responsible for giving notice shall ensure that it is published in a newspaper of general circulation within the City. The notice shall be published:";
const DEADLINE_SOURCE: &str = "At least 15 days prior to a public hearing being held before the Buildings, Safety Engineering, and Environmental Department; or";

fn cited(source: &str) -> SourceSpan {
    SourceSpan::cite(SNAPSHOT, DOCUMENT, NODE, source, 0, source.len())
        .expect("the reviewed source span is nonempty and UTF-8 aligned")
}

fn minimum_notice_period() -> Constraint<Duration> {
    Constraint::Interval(
        Interval::new(Bound::Included(Duration::days(15)), Bound::Unbounded)
            .expect("the statutory interval is ordered and nonempty"),
    )
}

fn individual(id: &str, concepts: &[&str]) -> Individual {
    Individual {
        id: IndividualId::from(id),
        concepts: concepts
            .iter()
            .map(|value| ConceptId::from(*value))
            .collect(),
    }
}

fn fact(subject: &str, relation: &str, object: &str) -> Fact {
    Fact {
        subject: IndividualId::from(subject),
        relation: RelationId::from(relation),
        object: IndividualId::from(object),
    }
}

fn notice_ontology() -> Ontology {
    let mut ontology = Ontology::new();
    for concept in ["Agency", "HearingForum", "PublishedNotice", "PublicHearing"] {
        ontology.declare_concept(ConceptId::from(concept));
    }
    for (id, domain, range) in [
        ("responsibleFor", "Agency", "PublishedNotice"),
        ("forumFor", "HearingForum", "PublicHearing"),
        ("noticeFor", "PublishedNotice", "PublicHearing"),
        ("precedes", "PublishedNotice", "PublicHearing"),
    ] {
        ontology
            .declare_relation(RelationDefinition {
                id: RelationId::from(id),
                domain: ConceptId::from(domain),
                range: ConceptId::from(range),
            })
            .unwrap();
    }
    for item in [
        individual("detroit:BSEED", &["Agency", "HearingForum"]),
        individual("case:notice", &["PublishedNotice"]),
        individual("case:hearing", &["PublicHearing"]),
    ] {
        ontology.declare_individual(item).unwrap();
    }
    for item in required_facts() {
        ontology.assert_fact(item).unwrap();
    }
    ontology
}

fn required_facts() -> BTreeSet<Fact> {
    BTreeSet::from([
        fact("detroit:BSEED", "responsibleFor", "case:notice"),
        fact("detroit:BSEED", "forumFor", "case:hearing"),
        fact("case:notice", "noticeFor", "case:hearing"),
        fact("case:notice", "precedes", "case:hearing"),
    ])
}

fn applies_to(ontology: &Ontology) -> bool {
    required_facts().iter().all(|item| ontology.contains(item))
}

fn rule() -> LegalRule<NoticePeriod> {
    LegalRule::new(
        RuleId("detroit:article-iii:block:79:proposition:1".into()),
        vec![cited(DEADLINE_SOURCE), cited(APPLICABILITY_SOURCE)],
        RuleStatus::Verified,
    )
}

fn evaluate(
    ontology: &Ontology,
    elapsed_notice: Duration,
) -> Option<Result<NoticePeriod, RefinementError>> {
    applies_to(ontology).then(|| Refined::verify(elapsed_notice, minimum_notice_period()))
}

fn main() {
    let declaration = rule();
    let ontology = notice_ontology();
    let fourteen_days = evaluate(&ontology, Duration::days(14));
    let fifteen_days = evaluate(&ontology, Duration::days(15));

    println!("Rule: {}", declaration.id.0);
    println!("Status: {:?}", declaration.status);
    println!("Sources: {} exact spans", declaration.sources.len());
    println!("Ontology: {} validated facts", ontology.facts().len());
    println!(
        "14 days: {}",
        if matches!(fourteen_days, Some(Ok(_))) {
            "passes"
        } else {
            "fails"
        }
    );
    println!(
        "15 days: {}",
        if matches!(fifteen_days, Some(Ok(_))) {
            "passes"
        } else {
            "fails"
        }
    );
}

#[cfg(test)]
mod tests {
    use super::{Duration, evaluate, notice_ontology, rule};

    #[test]
    fn exact_boundary_is_included() {
        let ontology = notice_ontology();
        assert!(matches!(
            evaluate(&ontology, Duration::days(14)),
            Some(Err(_))
        ));
        assert!(matches!(
            evaluate(&ontology, Duration::days(15)),
            Some(Ok(_))
        ));
        assert!(matches!(
            evaluate(&ontology, Duration::days(16)),
            Some(Ok(_))
        ));
    }

    #[test]
    fn declaration_retains_both_reviewed_sources() {
        let declaration = rule();
        assert_eq!(declaration.sources.len(), 2);
        assert!(
            declaration
                .sources
                .iter()
                .all(|source| source.verify(&source.quote).is_ok())
        );
    }
}
