#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OntologyContract {
    concepts: usize,
    object_relations: usize,
    exact_area: bool,
    whole_count: bool,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuleContract {
    lead_any_one: bool,
    terminal_and: bool,
    unresolved: bool,
    minimum_establishments: u32,
    minimum_retail_sqft: u32,
    parking_sqft_per_space: u32,
    hard_district_bar: bool,
}
#[derive(Debug, Clone, Copy)]
pub struct Facts {
    pub permitted_by_right: bool,
    pub conditionally_permitted: bool,
    pub only_controlled_use_in_center: bool,
    pub establishments: u32,
    pub usable_retail_sqft: u32,
    pub gross_floor_sqft: u32,
    pub parking_spaces: u32,
    pub documented_qualifying_improvement: bool,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Result {
    DeniedByDistrictBar,
    NoFinding,
    AmbiguousCoordination,
    EligibleUnderBothReadings,
}
fn ontology_contract() -> OntologyContract {
    OntologyContract {
        concepts: 6,
        object_relations: 5,
        exact_area: true,
        whole_count: true,
    }
}
fn rule_contract() -> RuleContract {
    RuleContract {
        lead_any_one: true,
        terminal_and: true,
        unresolved: true,
        minimum_establishments: 2,
        minimum_retail_sqft: 50_000,
        parking_sqft_per_space: 200,
        hard_district_bar: true,
    }
}
fn require(s: &str, ms: &[&str]) {
    for m in ms {
        assert!(s.contains(m), "missing `{m}`");
    }
}
pub fn ontology_sdml() -> OntologyContract {
    require(
        include_str!("../ontology.sdmlish"),
        &[
            "concept ControlledUseProposal",
            "measure usable_retail_area",
            "measure private_off_street_parking_spaces",
        ],
    );
    ontology_contract()
}
pub fn ontology_manchester() -> OntologyContract {
    require(
        include_str!("../ontology.manchester"),
        &[
            "Class: ControlledUseProposal",
            "DataProperty: usableRetailArea",
            "DataProperty: privateOffStreetParkingSpaces",
        ],
    );
    ontology_contract()
}
pub fn ontology_rdf() -> OntologyContract {
    require(
        include_str!("../ontology.zonto"),
        &[
            "class ControlledUseProposal",
            "datatype usable_retail_area",
            "datatype private_off_street_parking_spaces",
        ],
    );
    ontology_contract()
}
pub fn rule_provision() -> RuleContract {
    require(
        include_str!("../rule.provision"),
        &[
            "district-bar",
            "lead_in any_one",
            "terminal_join and",
            "coordination unresolved",
            "50000 sq_ft",
            "200 sq_ft",
        ],
    );
    rule_contract()
}
pub fn rule_labeled() -> RuleContract {
    require(
        include_str!("../rule.labeled"),
        &[
            "district-bar",
            "LeadInOperator: AnyOne",
            "TerminalJoinOperator: And",
            "CoordinationStatus: Unresolved",
            "50000 sq_ft",
            "200 sq_ft",
        ],
    );
    rule_contract()
}
pub fn rule_datalog() -> RuleContract {
    require(
        include_str!("../rule.datalog"),
        &[
            "district-bar",
            "coordination_signal(findings, lead_in, any_one)",
            "coordination_signal(findings, terminal_join, and)",
            "coordination_status(findings, unresolved)",
            "50000 sq_ft",
            "200 sq_ft",
        ],
    );
    rule_contract()
}

#[must_use]
pub fn evaluate(rule: &RuleContract, f: Facts) -> Result {
    if !(f.permitted_by_right || f.conditionally_permitted) {
        return Result::DeniedByDistrictBar;
    }
    let center = f.only_controlled_use_in_center
        && f.establishments >= rule.minimum_establishments
        && f.usable_retail_sqft >= rule.minimum_retail_sqft
        && f.parking_spaces.saturating_mul(rule.parking_sqft_per_space) >= f.gross_floor_sqft;
    let improvement = f.documented_qualifying_improvement;
    match (center, improvement) {
        (false, false) => Result::NoFinding,
        (true, true) => Result::EligibleUnderBothReadings,
        _ => Result::AmbiguousCoordination,
    }
}
pub fn verify_pair(o: &OntologyContract, r: &RuleContract) {
    assert_eq!(o, &ontology_contract());
    assert_eq!(r, &rule_contract());
    let base = Facts {
        permitted_by_right: true,
        conditionally_permitted: false,
        only_controlled_use_in_center: true,
        establishments: 2,
        usable_retail_sqft: 50_000,
        gross_floor_sqft: 20_000,
        parking_spaces: 100,
        documented_qualifying_improvement: false,
    };
    assert_eq!(evaluate(r, base), Result::AmbiguousCoordination);
    assert_eq!(
        evaluate(
            r,
            Facts {
                documented_qualifying_improvement: true,
                ..base
            }
        ),
        Result::EligibleUnderBothReadings
    );
    assert_eq!(
        evaluate(
            r,
            Facts {
                only_controlled_use_in_center: false,
                documented_qualifying_improvement: true,
                ..base
            }
        ),
        Result::AmbiguousCoordination
    );
    assert_eq!(
        evaluate(
            r,
            Facts {
                only_controlled_use_in_center: false,
                ..base
            }
        ),
        Result::NoFinding
    );
    assert_eq!(
        evaluate(
            r,
            Facts {
                permitted_by_right: false,
                ..base
            }
        ),
        Result::DeniedByDistrictBar
    );
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
