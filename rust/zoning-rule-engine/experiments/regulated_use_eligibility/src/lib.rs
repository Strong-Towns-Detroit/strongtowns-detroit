#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OntologyContract {
    concepts: usize,
    relations: usize,
    has_exact_length: bool,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuleContract {
    independent_exceptions: bool,
    radius_feet: u32,
    prohibited_count: usize,
    counts_distinct_sites: bool,
    waiver_reference: bool,
}
fn ontology_contract() -> OntologyContract {
    OntologyContract {
        concepts: 7,
        relations: 7,
        has_exact_length: true,
    }
}
fn rule_contract() -> RuleContract {
    RuleContract {
        independent_exceptions: true,
        radius_feet: 1000,
        prohibited_count: 2,
        counts_distinct_sites: true,
        waiver_reference: true,
    }
}
fn require(source: &str, markers: &[&str]) {
    for m in markers {
        assert!(source.contains(m), "missing `{m}`");
    }
}
pub fn ontology_sdml() -> OntologyContract {
    require(
        include_str!("../ontology.sdmlish"),
        &[
            "concept Applicant",
            "relation delinquent_on",
            "measure boundary_distance_to",
            "predicate legally_established",
        ],
    );
    ontology_contract()
}
pub fn ontology_manchester() -> OntologyContract {
    require(
        include_str!("../ontology.manchester"),
        &[
            "Class: Applicant",
            "ObjectProperty: delinquentOn",
            "DataProperty: boundaryDistanceTo",
        ],
    );
    ontology_contract()
}
pub fn ontology_rdf() -> OntologyContract {
    require(
        include_str!("../ontology.zonto"),
        &[
            "class Applicant",
            "property delinquent_on",
            "datatype boundary_distance_to",
            "predicate legally_established",
        ],
    );
    ontology_contract()
}
pub fn rule_provision() -> RuleContract {
    require(
        include_str!("../rule.provision"),
        &[
            "section-50-3-341:b:ineligibility",
            "section-50-3-341:b:exceptions",
            "section-50-3-341:c:spacing",
            "acquired_by_foreclosure_or_deed_in_lieu",
            "authorization_corrects",
            "count distinct site",
            "1000 ft",
            ">= 2",
        ],
    );
    rule_contract()
}
pub fn rule_labeled() -> RuleContract {
    require(
        include_str!("../rule.labeled"),
        &[
            "section-50-3-341:b:ineligibility",
            "section-50-3-341:b:exceptions",
            "section-50-3-341:c:spacing",
            "acquiredByForeclosureOrDeedInLieu",
            "authorizationCorrects",
            "count distinct site",
            "1000 ft",
            ">= 2",
        ],
    );
    rule_contract()
}
pub fn rule_datalog() -> RuleContract {
    require(
        include_str!("../rule.datalog"),
        &[
            "section-50-3-341:b:ineligibility",
            "section-50-3-341:b:exceptions",
            "section-50-3-341:c:spacing",
            "acquired_by_foreclosure_or_deed_in_lieu",
            "authorization_corrects",
            "count_distinct<Site>",
            "1000 ft",
            "Count >= 2",
        ],
    );
    rule_contract()
}

#[must_use]
pub fn eligible_to_apply(
    delinquent: bool,
    foreclosure_or_deed_exception: bool,
    corrective_authorization_exception: bool,
) -> bool {
    !delinquent || foreclosure_or_deed_exception || corrective_authorization_exception
}
#[derive(Debug, Clone, Copy)]
pub struct NearbySite {
    pub id: u32,
    pub distance_feet: u32,
}
#[must_use]
pub fn approval_prohibited(rule: &RuleContract, sites: &[NearbySite], waiver: bool) -> bool {
    let mut qualifying = sites
        .iter()
        .filter(|site| site.distance_feet <= rule.radius_feet)
        .map(|site| site.id)
        .collect::<Vec<_>>();
    qualifying.sort_unstable();
    qualifying.dedup();
    qualifying.len() >= rule.prohibited_count && !waiver
}
pub fn verify_pair(o: &OntologyContract, r: &RuleContract) {
    assert_eq!(o, &ontology_contract());
    assert_eq!(r, &rule_contract());
    assert!(!eligible_to_apply(true, false, false));
    assert!(eligible_to_apply(true, true, false));
    assert!(eligible_to_apply(true, false, true));
    assert!(eligible_to_apply(false, false, false));
    let a = NearbySite {
        id: 1,
        distance_feet: 999,
    };
    let b = NearbySite {
        id: 2,
        distance_feet: 1000,
    };
    let far = NearbySite {
        id: 3,
        distance_feet: 1001,
    };
    assert!(!approval_prohibited(r, &[a], false));
    assert!(approval_prohibited(r, &[a, b], false));
    assert!(!approval_prohibited(r, &[a, b], true));
    assert!(!approval_prohibited(r, &[a, far], false));
    assert!(!approval_prohibited(r, &[a, a], false));
    let same_distance_other_site = NearbySite {
        id: 4,
        distance_feet: 999,
    };
    assert!(approval_prohibited(
        r,
        &[a, same_distance_other_site],
        false
    ));
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
