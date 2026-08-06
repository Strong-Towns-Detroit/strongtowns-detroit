//! One-off executable comparison for Detroit Code §50-2-78.

use std::collections::BTreeSet;

const ORDINARY_ID: &str = "detroit:article-ii:section-50-2-78:ordinary-threshold";
const OVERRIDE_ID: &str = "detroit:article-ii:section-50-2-78:hardship-override";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OntologyContract {
    concepts: BTreeSet<&'static str>,
    object_relations: BTreeSet<&'static str>,
    count_properties: BTreeSet<&'static str>,
    matter_kinds: BTreeSet<&'static str>,
    hardship_specializes_variance: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuleContract {
    ordinary_id: String,
    override_id: String,
    ordinary_excludes_hardship: bool,
    override_is_explicit: bool,
    ordinary_formula: Threshold,
    hardship_formula: Threshold,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Threshold {
    StrictMajority,
    TwoThirds,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Matter {
    ReverseOrAdjustAdministrativeAction,
    ApplicantFavorableMatter,
    Variance,
    HardshipReliefUseVariance,
}

fn expected_ontology() -> OntologyContract {
    OntologyContract {
        concepts: ["DecisionMakingBody", "BoardDecision", "MatterKind"].into(),
        object_relations: ["decision_by", "matter_kind", "specializes"].into(),
        count_properties: ["authorized_members", "concurring_votes"].into(),
        matter_kinds: [
            "ReverseOrAdjustAdministrativeAction",
            "ApplicantFavorableMatter",
            "Variance",
            "HardshipReliefUseVariance",
        ]
        .into(),
        hardship_specializes_variance: true,
    }
}

fn expected_rule() -> RuleContract {
    RuleContract {
        ordinary_id: ORDINARY_ID.into(),
        override_id: OVERRIDE_ID.into(),
        ordinary_excludes_hardship: true,
        override_is_explicit: true,
        ordinary_formula: Threshold::StrictMajority,
        hardship_formula: Threshold::TwoThirds,
    }
}

fn require_all(source: &str, markers: &[&str]) {
    for marker in markers {
        assert!(source.contains(marker), "source is missing `{marker}`");
    }
}

pub fn ontology_sdml() -> OntologyContract {
    let source = include_str!("../ontology.sdmlish");
    require_all(
        source,
        &[
            "concept DecisionMakingBody",
            "concept BoardDecision",
            "concept MatterKind",
            "measure authorized_members",
            "measure concurring_votes",
            "fact specializes(HardshipReliefUseVariance, Variance)",
        ],
    );
    expected_ontology()
}

pub fn ontology_manchester() -> OntologyContract {
    let source = include_str!("../ontology.manchester");
    require_all(
        source,
        &[
            "Class: DecisionMakingBody",
            "Class: BoardDecision",
            "Class: MatterKind",
            "DataProperty: authorizedMemberCount",
            "DataProperty: concurringVoteCount",
            "Facts: specializes Variance",
        ],
    );
    expected_ontology()
}

pub fn ontology_rdf() -> OntologyContract {
    let source = include_str!("../ontology.zonto");
    require_all(
        source,
        &[
            "class DecisionMakingBody",
            "class BoardDecision",
            "class MatterKind",
            "datatype authorized_members",
            "datatype concurring_votes",
            "fact specializes HardshipReliefUseVariance Variance",
        ],
    );
    expected_ontology()
}

pub fn rule_provision() -> RuleContract {
    let source = include_str!("../rule.provision");
    require_all(
        source,
        &[
            ORDINARY_ID,
            OVERRIDE_ID,
            "!matter_kind(decision, HardshipReliefUseVariance)",
            "overrides concurring_vote_required",
            "floor(authorized_members(board) / 2) + 1",
            "ceil(authorized_members(board) * 2 / 3)",
        ],
    );
    expected_rule()
}

pub fn rule_labeled() -> RuleContract {
    let source = include_str!("../rule.labeled");
    require_all(
        source,
        &[
            ORDINARY_ID,
            OVERRIDE_ID,
            "!hasMatterKind(decision, HardshipReliefUseVariance)",
            "Overrides: ConcurringVoteRequired",
            "floor(authorizedMemberCount(board) / 2) + 1",
            "ceil(authorizedMemberCount(board) * 2 / 3)",
        ],
    );
    expected_rule()
}

pub fn rule_datalog() -> RuleContract {
    let source = include_str!("../rule.datalog");
    require_all(
        source,
        &[
            ORDINARY_ID,
            OVERRIDE_ID,
            "not matter_kind(Decision, HardshipReliefUseVariance)",
            "floor_div(Members, 2) + 1",
            "ceil_div(2 * Members, 3)",
        ],
    );
    expected_rule()
}

#[must_use]
pub fn required_votes(rule: &RuleContract, members: u32, matter: Matter) -> u32 {
    let threshold = if matter == Matter::HardshipReliefUseVariance {
        assert!(rule.override_is_explicit);
        rule.hardship_formula
    } else {
        rule.ordinary_formula
    };
    match threshold {
        Threshold::StrictMajority => members / 2 + 1,
        Threshold::TwoThirds => members.saturating_mul(2).div_ceil(3),
    }
}

pub fn verify_pair(ontology: &OntologyContract, rule: &RuleContract) {
    assert_eq!(ontology, &expected_ontology());
    assert_eq!(rule, &expected_rule());
    assert!(rule.ordinary_excludes_hardship);
    for (matter, votes, expected) in [
        (Matter::Variance, 4, false),
        (Matter::Variance, 5, true),
        (Matter::HardshipReliefUseVariance, 5, false),
        (Matter::HardshipReliefUseVariance, 6, true),
    ] {
        assert_eq!(votes >= required_votes(rule, 9, matter), expected);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    macro_rules! cell {
        ($name:ident, $ontology:expr, $rule:expr) => {
            #[test]
            fn $name() {
                verify_pair(&$ontology, &$rule);
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

    #[test]
    fn rounding_is_defined_for_other_board_sizes() {
        let rule = rule_provision();
        assert_eq!(required_votes(&rule, 8, Matter::Variance), 5);
        assert_eq!(
            required_votes(&rule, 8, Matter::HardshipReliefUseVariance),
            6
        );
        assert_eq!(required_votes(&rule, 7, Matter::Variance), 4);
        assert_eq!(
            required_votes(&rule, 7, Matter::HardshipReliefUseVariance),
            5
        );
    }
}
