//! Executable proof obligations for the shared §50-3-10 fixture.
//!
//! This deliberately consumes a canonical signature, not any surface syntax.
//! Each ontology parser must emit this signature; each rule parser imports it.

#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd)]
pub enum Concept {
    Agency,
    HearingForum,
    PublishedNotice,
    PublicHearing,
    LegalRequirement,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Relation {
    pub name: &'static str,
    pub domain: Concept,
    pub range: Concept,
}

pub const REQUIRED_CONCEPTS: [Concept; 5] = [
    Concept::Agency,
    Concept::HearingForum,
    Concept::PublishedNotice,
    Concept::PublicHearing,
    Concept::LegalRequirement,
];

pub const REQUIRED_RELATIONS: [Relation; 5] = [
    Relation { name: "responsible_for", domain: Concept::Agency, range: Concept::PublishedNotice },
    Relation { name: "notice_for", domain: Concept::PublishedNotice, range: Concept::PublicHearing },
    Relation { name: "forum_for", domain: Concept::HearingForum, range: Concept::PublicHearing },
    Relation { name: "required_by", domain: Concept::PublishedNotice, range: Concept::LegalRequirement },
    Relation { name: "precedes", domain: Concept::PublishedNotice, range: Concept::PublicHearing },
];

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CanonicalOntology {
    pub concepts: Vec<Concept>,
    pub relations: Vec<Relation>,
    pub bseed_types: Vec<Concept>,
}

impl CanonicalOntology {
    pub fn fixture() -> Self {
        Self {
            concepts: REQUIRED_CONCEPTS.to_vec(),
            relations: REQUIRED_RELATIONS.to_vec(),
            bseed_types: vec![Concept::Agency, Concept::HearingForum],
        }
    }

    /// Corpus-relative adequacy: every symbol demanded by the reviewed fixture
    /// exists with exactly the required type signature.
    pub fn proves_fixture_adequacy(&self) -> bool {
        REQUIRED_CONCEPTS.iter().all(|c| self.concepts.contains(c))
            && REQUIRED_RELATIONS.iter().all(|r| self.relations.contains(r))
            && [Concept::Agency, Concept::HearingForum]
                .iter().all(|c| self.bseed_types.contains(c))
    }

    pub fn well_typed_fact(&self, relation: &str, subject: Concept, object: Concept) -> bool {
        self.relations.iter().any(|r| {
            r.name == relation && r.domain == subject && r.range == object
        })
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RuleCertificate {
    pub proposition_id: &'static str,
    pub source_spans: [&'static str; 2],
    pub minimum_days_inclusive: u32,
    pub strict: bool,
    pub defeasible: bool,
    pub exceptions: usize,
}

pub const EXPECTED_RULE: RuleCertificate = RuleCertificate {
    proposition_id: "detroit:article-iii:block:79:proposition:1",
    source_spans: ["§50-3-10", "§50-3-10(1)"],
    minimum_days_inclusive: 15,
    strict: true,
    defeasible: false,
    exceptions: 0,
};

pub const fn notice_complies(elapsed_days: u32) -> bool {
    elapsed_days >= EXPECTED_RULE.minimum_days_inclusive
}

/// Observable equivalence for this fixture: parsers are equivalent when their
/// canonical ontology and rule certificates are equal. This is intentionally
/// stronger than comparing their answers for only 14/15/16 days.
pub fn equivalent(
    left_ontology: &CanonicalOntology,
    left_rule: &RuleCertificate,
    right_ontology: &CanonicalOntology,
    right_rule: &RuleCertificate,
) -> bool {
    left_ontology == right_ontology && left_rule == right_rule
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixture_is_corpus_relatively_adequate() {
        assert!(CanonicalOntology::fixture().proves_fixture_adequacy());
    }

    #[test]
    fn domain_and_range_are_enforced() {
        let o = CanonicalOntology::fixture();
        assert!(o.well_typed_fact("responsible_for", Concept::Agency, Concept::PublishedNotice));
        assert!(!o.well_typed_fact("responsible_for", Concept::PublicHearing, Concept::Agency));
    }

    #[test]
    fn inclusive_boundary_is_exhaustively_checked_near_the_threshold() {
        assert!(!notice_complies(14));
        assert!(notice_complies(15));
        assert!(notice_complies(16));
    }

    #[test]
    fn a_missing_term_fails_adequacy() {
        let mut o = CanonicalOntology::fixture();
        o.relations.retain(|r| r.name != "required_by");
        assert!(!o.proves_fixture_adequacy());
    }

    #[test]
    fn equivalence_detects_semantic_drift_not_just_behavioral_examples() {
        let o = CanonicalOntology::fixture();
        let mut weakened = EXPECTED_RULE.clone();
        weakened.strict = false;
        assert!(!equivalent(&o, &EXPECTED_RULE, &o, &weakened));
    }
}

