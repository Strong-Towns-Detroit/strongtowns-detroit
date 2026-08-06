use std::collections::BTreeMap;

use manchester_style_experiment::{
    compile_ontology, evaluate, parse_ontology, parse_rule, typecheck,
};
use zoning_rule_engine::{ConceptId, Duration, Fact, Individual, IndividualId, RelationId};

fn main() {
    let schema = parse_ontology(include_str!("../ontology.manchester")).expect("valid ontology");
    let provision = parse_rule(include_str!("../article_iii.rule")).expect("valid rule");
    typecheck(&schema, &provision).expect("type-correct rule");
    let mut ontology = compile_ontology(&schema).expect("compiled ontology");
    for (id, concept) in [
        ("case:notice", "PublishedNotice"),
        ("case:hearing", "PublicHearing"),
    ] {
        ontology
            .declare_individual(Individual {
                id: IndividualId::from(id),
                concepts: [ConceptId::from(concept)].into(),
            })
            .unwrap();
    }
    for (subject, relation, object) in [
        ("Chapter50", "requiresPublishedNotice", "case:notice"),
        ("BSEED", "responsibleFor", "case:notice"),
        ("BSEED", "forumFor", "case:hearing"),
        ("case:notice", "noticeFor", "case:hearing"),
        ("case:notice", "precedes", "case:hearing"),
    ] {
        ontology
            .assert_fact(Fact {
                subject: IndividualId::from(subject),
                relation: RelationId::from(relation),
                object: IndividualId::from(object),
            })
            .unwrap();
    }
    let bindings = BTreeMap::from([
        ("regime".into(), "Chapter50".into()),
        ("agency".into(), "BSEED".into()),
        ("notice".into(), "case:notice".into()),
        ("hearing".into(), "case:hearing".into()),
    ]);
    println!("{} {}", provision.proposition_id, provision.citation);
    for (role, quote) in &provision.source_spans {
        println!("{role}: {quote}");
    }
    for days in [14, 15, 16] {
        let passes = matches!(
            evaluate(&provision, &ontology, &bindings, Duration::days(days)),
            Some(Ok(_))
        );
        println!("{days} days: {}", if passes { "passes" } else { "fails" });
    }
}
