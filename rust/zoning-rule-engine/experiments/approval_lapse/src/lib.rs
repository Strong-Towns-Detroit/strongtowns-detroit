use std::collections::BTreeSet;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OntologyContract {
    concepts: BTreeSet<&'static str>,
    relations: BTreeSet<&'static str>,
    dates: BTreeSet<&'static str>,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuleContract {
    initial_months: u8,
    maximum_months_from_grant: u8,
    extension_bar_has_precedence: bool,
    renewal_requires_application_and_hearing: bool,
}
#[derive(Debug, Clone, Copy)]
pub struct GrantFacts {
    pub permit_obtained_month: Option<u8>,
    pub extension_until_month: Option<u8>,
    pub extension_authorized: bool,
    pub unlawfully_established_then_legalized: bool,
}

fn ontology_contract() -> OntologyContract {
    OntologyContract {
        concepts: [
            "RegulatedUseGrant",
            "RegulatedUse",
            "Permit",
            "Extension",
            "Application",
            "PublicHearing",
            "DecisionMakingBody",
        ]
        .into(),
        relations: [
            "grant_for",
            "permit_under",
            "extension_of",
            "authorized_by",
            "new_application_for",
            "hearing_for",
        ]
        .into(),
        dates: ["granted_at", "obtained_at", "extended_until"].into(),
    }
}
fn rule_contract() -> RuleContract {
    RuleContract {
        initial_months: 6,
        maximum_months_from_grant: 18,
        extension_bar_has_precedence: true,
        renewal_requires_application_and_hearing: true,
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
            "concept RegulatedUseGrant",
            "relation extension_of",
            "measure extended_until",
            "predicate unlawfully_established_or_expanded",
        ],
    );
    ontology_contract()
}
pub fn ontology_manchester() -> OntologyContract {
    require(
        include_str!("../ontology.manchester"),
        &[
            "Class: RegulatedUseGrant",
            "ObjectProperty: extensionOf",
            "DataProperty: extendedUntil",
        ],
    );
    ontology_contract()
}
pub fn ontology_rdf() -> OntologyContract {
    require(
        include_str!("../ontology.zonto"),
        &[
            "class RegulatedUseGrant",
            "property extension_of",
            "datatype extended_until",
            "predicate unlawfully_established_or_expanded",
        ],
    );
    ontology_contract()
}
pub fn rule_provision() -> RuleContract {
    require(
        include_str!("../rule.provision"),
        &[
            "section-50-3-386:lapse",
            "section-50-3-386:extension",
            "section-50-3-386:notwithstanding",
            "section-50-3-386:no-additional-extension",
            "overrides one_bounded_extension",
            "new_application_for",
            "hearing_for",
        ],
    );
    rule_contract()
}
pub fn rule_labeled() -> RuleContract {
    require(
        include_str!("../rule.labeled"),
        &[
            "section-50-3-386:lapse",
            "section-50-3-386:extension",
            "section-50-3-386:notwithstanding",
            "section-50-3-386:no-additional-extension",
            "Overrides: OneBoundedExtension",
            "newApplicationFor",
            "hearingFor",
        ],
    );
    rule_contract()
}
pub fn rule_datalog() -> RuleContract {
    require(
        include_str!("../rule.datalog"),
        &[
            "section-50-3-386:lapse",
            "section-50-3-386:extension",
            "section-50-3-386:notwithstanding",
            "section-50-3-386:no-additional-extension",
            "not extension_barred",
            "new_application_for",
            "hearing_for",
        ],
    );
    rule_contract()
}

#[must_use]
pub fn effective_deadline(rule: &RuleContract, facts: GrantFacts) -> u8 {
    let valid = facts.extension_authorized
        && !facts.unlawfully_established_then_legalized
        && facts
            .extension_until_month
            .is_some_and(|month| month <= rule.maximum_months_from_grant);
    if valid {
        facts.extension_until_month.unwrap_or(rule.initial_months)
    } else {
        rule.initial_months
    }
}
#[must_use]
pub fn is_null_and_void(rule: &RuleContract, facts: GrantFacts, current_month: u8) -> bool {
    let deadline = effective_deadline(rule, facts);
    let timely_permit = facts
        .permit_obtained_month
        .is_some_and(|month| month <= deadline);
    current_month > deadline && !timely_permit
}
#[must_use]
pub fn may_proceed_anew(application_filed: bool, hearing_held: bool) -> bool {
    application_filed && hearing_held
}

pub fn verify_pair(ontology: &OntologyContract, rule: &RuleContract) {
    assert_eq!(ontology, &ontology_contract());
    assert_eq!(rule, &rule_contract());
    let none = GrantFacts {
        permit_obtained_month: None,
        extension_until_month: None,
        extension_authorized: false,
        unlawfully_established_then_legalized: false,
    };
    assert!(!is_null_and_void(rule, none, 6));
    assert!(is_null_and_void(rule, none, 7));
    let permit = GrantFacts {
        permit_obtained_month: Some(6),
        ..none
    };
    assert!(!is_null_and_void(rule, permit, 20));
    let extended = GrantFacts {
        extension_until_month: Some(18),
        extension_authorized: true,
        ..none
    };
    assert!(!is_null_and_void(rule, extended, 18));
    assert!(is_null_and_void(rule, extended, 19));
    let too_long = GrantFacts {
        extension_until_month: Some(19),
        extension_authorized: true,
        ..none
    };
    assert_eq!(effective_deadline(rule, too_long), 6);
    let barred = GrantFacts {
        unlawfully_established_then_legalized: true,
        ..extended
    };
    assert_eq!(effective_deadline(rule, barred), 6);
    assert!(!may_proceed_anew(true, false));
    assert!(may_proceed_anew(true, true));
}

#[cfg(test)]
mod tests {
    use super::*;
    macro_rules! cell {
        ($n:ident,$o:expr,$r:expr) => {
            #[test]
            fn $n() {
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
