use std::collections::BTreeSet;

const ORDINARY_ID: &str = "detroit:article-ii:section-50-2-79:ordinary-finality";
const EXCEPTION_ID: &str = "detroit:article-ii:section-50-2-79:immediate-effect-exception";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OntologyContract {
    concepts: BTreeSet<&'static str>,
    relations: BTreeSet<&'static str>,
    datetime_property: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuleContract {
    ordinary_id: &'static str,
    exception_id: &'static str,
    business_days: u8,
    final_minute: u16,
    exception_requires_finding: bool,
    exception_requires_certification: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LocalMoment {
    /// Arbitrary consecutive civil-day index used by this one-off fixture.
    pub day: i32,
    /// Monday = 0 through Sunday = 6.
    pub weekday: u8,
    pub minute: u16,
}

#[derive(Debug, Clone, Copy)]
pub struct ImmediateEffectFacts {
    pub necessity_finding: bool,
    pub preserves_property_or_personal_rights: bool,
    pub certified_on_record: bool,
}

fn ontology_contract() -> OntologyContract {
    OntologyContract {
        concepts: [
            "DecisionMakingBody",
            "BoardDecision",
            "BoardVote",
            "NecessityFinding",
            "RecordCertification",
        ]
        .into(),
        relations: [
            "decision_by",
            "rendered_by_vote",
            "finding_for",
            "certified_by",
        ]
        .into(),
        datetime_property: "occurred_at",
    }
}

fn rule_contract() -> RuleContract {
    RuleContract {
        ordinary_id: ORDINARY_ID,
        exception_id: EXCEPTION_ID,
        business_days: 3,
        final_minute: 16 * 60,
        exception_requires_finding: true,
        exception_requires_certification: true,
    }
}

fn require(source: &str, markers: &[&str]) {
    for marker in markers {
        assert!(source.contains(marker), "missing `{marker}`");
    }
}

pub fn ontology_sdml() -> OntologyContract {
    require(
        include_str!("../ontology.sdmlish"),
        &[
            "concept BoardDecision",
            "concept NecessityFinding",
            "relation certified_by",
            "measure occurred_at",
        ],
    );
    ontology_contract()
}
pub fn ontology_manchester() -> OntologyContract {
    require(
        include_str!("../ontology.manchester"),
        &[
            "Class: BoardDecision",
            "Class: NecessityFinding",
            "ObjectProperty: certifiedBy",
            "DataProperty: occurredAt",
        ],
    );
    ontology_contract()
}
pub fn ontology_rdf() -> OntologyContract {
    require(
        include_str!("../ontology.zonto"),
        &[
            "class BoardDecision",
            "class NecessityFinding",
            "property certified_by",
            "datatype occurred_at",
        ],
    );
    ontology_contract()
}
pub fn rule_provision() -> RuleContract {
    require(
        include_str!("../rule.provision"),
        &[
            ORDINARY_ID,
            EXCEPTION_ID,
            "add_business_days",
            "16:00",
            "necessary_to_preserve",
            "certified_by",
            "overrides ordinary_finality",
        ],
    );
    rule_contract()
}
pub fn rule_labeled() -> RuleContract {
    require(
        include_str!("../rule.labeled"),
        &[
            ORDINARY_ID,
            EXCEPTION_ID,
            "addBusinessDays",
            "16:00",
            "necessaryToPreserve",
            "certifiedBy",
            "Overrides: OrdinaryFinality",
        ],
    );
    rule_contract()
}
pub fn rule_datalog() -> RuleContract {
    require(
        include_str!("../rule.datalog"),
        &[
            ORDINARY_ID,
            EXCEPTION_ID,
            "add_business_days",
            "16:00",
            "necessary_to_preserve",
            "certified_by",
            "not immediate_effect_authorized",
        ],
    );
    rule_contract()
}

fn add_business_days(mut moment: LocalMoment, count: u8) -> LocalMoment {
    let mut added = 0;
    while added < count {
        moment.day += 1;
        moment.weekday = (moment.weekday + 1) % 7;
        if moment.weekday < 5 {
            added += 1;
        }
    }
    moment
}

#[must_use]
pub fn final_at(
    rule: &RuleContract,
    vote: LocalMoment,
    facts: ImmediateEffectFacts,
) -> LocalMoment {
    let immediate = facts.necessity_finding
        && facts.preserves_property_or_personal_rights
        && facts.certified_on_record;
    if immediate {
        vote
    } else {
        let mut result = add_business_days(vote, rule.business_days);
        result.minute = rule.final_minute;
        result
    }
}

pub fn verify_pair(ontology: &OntologyContract, rule: &RuleContract) {
    assert_eq!(ontology, &ontology_contract());
    assert_eq!(rule, &rule_contract());
    let friday_vote = LocalMoment {
        day: 0,
        weekday: 4,
        minute: 11 * 60,
    };
    let none = ImmediateEffectFacts {
        necessity_finding: false,
        preserves_property_or_personal_rights: false,
        certified_on_record: false,
    };
    assert_eq!(
        final_at(rule, friday_vote, none),
        LocalMoment {
            day: 5,
            weekday: 2,
            minute: 16 * 60
        }
    );
    let finding_only = ImmediateEffectFacts {
        necessity_finding: true,
        preserves_property_or_personal_rights: true,
        certified_on_record: false,
    };
    assert_eq!(final_at(rule, friday_vote, finding_only).day, 5);
    let certified = ImmediateEffectFacts {
        certified_on_record: true,
        ..finding_only
    };
    assert_eq!(final_at(rule, friday_vote, certified), friday_vote);
}

#[cfg(test)]
mod tests {
    use super::*;
    macro_rules! cell {
        ($name:ident, $o:expr, $r:expr) => {
            #[test]
            fn $name() {
                verify_pair(&$o, &$r);
            }
        };
    }
    cell!(o1_r1, ontology_sdml(), rule_provision());
    cell!(o1_r2, ontology_sdml(), rule_labeled());
    cell!(o1_r3, ontology_sdml(), rule_datalog());
    cell!(o2_r1, ontology_manchester(), rule_provision());
    cell!(o2_r2, ontology_manchester(), rule_labeled());
    cell!(o2_r3, ontology_manchester(), rule_datalog());
    cell!(o3_r1, ontology_rdf(), rule_provision());
    cell!(o3_r2, ontology_rdf(), rule_labeled());
    cell!(o3_r3, ontology_rdf(), rule_datalog());
}
