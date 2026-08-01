pub const INVENTORY: &str = include_str!("../semantic_inventory.tsv");
pub const SOURCE_MANIFEST: &str = include_str!("../source_manifest.tsv");
pub const ONTOLOGY_SOURCE: &str = include_str!("../article_i.ontology");
pub const RULE_SOURCE: &str = include_str!("../article_i.rules");

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RuleSet { Chapter50, External, PrivateAgreement, PriorOrdinance }

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UseTableSource { ArticleXiiTable, ArticleEightToElevenList }

#[must_use]
pub const fn chapter_applies(land_in_city: bool, exempt_from_local_zoning: bool) -> bool {
    land_in_city && !exempt_from_local_zoning
}

#[must_use]
pub const fn controlling_public_rule(
    chapter_more_restrictive: bool,
    conflict_is_use_table_vs_use_list: bool,
) -> RuleSet {
    if conflict_is_use_table_vs_use_list {
        RuleSet::External // sentinel: use `controlling_use_source` for this special override
    } else if chapter_more_restrictive {
        RuleSet::Chapter50
    } else {
        RuleSet::External
    }
}

#[must_use]
pub const fn controlling_use_source(conflict: bool) -> UseTableSource {
    if conflict { UseTableSource::ArticleEightToElevenList } else { UseTableSource::ArticleXiiTable }
}

#[must_use]
pub const fn controlling_private_rule(chapter_more_restrictive: bool) -> RuleSet {
    if chapter_more_restrictive { RuleSet::Chapter50 } else { RuleSet::PrivateAgreement }
}

#[must_use]
pub const fn old_violation_continues(currently_complies: bool) -> bool { !currently_complies }

#[must_use]
pub const fn prior_nonconformity_continues(
    was_legal_nonconformity: bool,
    originating_situation_continues: bool,
    now_conforming: bool,
) -> bool {
    was_legal_nonconformity && originating_situation_continues && !now_conforming
}

#[must_use]
pub const fn may_extend_prior_approval(
    original_body: bool,
    findings_remain_valid: bool,
    prior_extensions: u8,
    requested_months: u8,
) -> bool {
    original_body && findings_remain_valid && prior_extensions == 0 && requested_months <= 12
}

#[must_use]
pub const fn may_choose_prior_rules(
    submitted_before_effective_date: bool,
    complete: bool,
    pending_on_effective_date: bool,
) -> bool {
    submitted_before_effective_date && complete && pending_on_effective_date
}

pub fn inventory_rows() -> impl Iterator<Item = Vec<&'static str>> {
    INVENTORY.lines().skip(1).filter(|line| !line.trim().is_empty())
        .map(|line| line.split('\t').collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeSet;

    #[test]
    fn every_article_i_span_has_unique_trace_and_disposition() {
        let rows: Vec<_> = inventory_rows().collect();
        assert_eq!(rows.len(), 47);
        let ids: BTreeSet<_> = rows.iter().map(|r| r[0]).collect();
        assert_eq!(ids.len(), rows.len());
        assert!(rows.iter().all(|r| r.len() == 7));
        assert!(rows.iter().all(|r| matches!(r[3], "executable" | "declarative" | "interpretive" | "reserved" | "unresolved")));
        assert!(rows.iter().all(|r| !r[4].is_empty() && !r[5].is_empty() && !r[6].is_empty()));
    }

    #[test]
    fn inventory_covers_every_section_and_reserved_range() {
        let refs: BTreeSet<_> = inventory_rows().map(|r| r[1]).collect();
        for n in 1..=15 {
            assert!(refs.contains(format!("§50-1-{n}").as_str()), "missing §50-1-{n}");
        }
        assert!(refs.contains("§§50-1-16—50-1-40"));
        let manifest_refs: BTreeSet<_> = SOURCE_MANIFEST.lines().skip(1)
            .filter(|line| !line.is_empty()).map(|line| line.split('\t').next().unwrap_or("")).collect();
        assert_eq!(refs, manifest_refs);
        assert!(SOURCE_MANIFEST.lines().skip(1).filter(|line| !line.is_empty()).all(|line| {
            let columns: Vec<_> = line.split('\t').collect();
            columns.len() == 3 && columns[2].len() == 64
        }));
    }

    #[test]
    fn authored_sources_expose_required_families() {
        for term in ["concept Land", "concept DistrictBoundary", "value ExtensionDuration: Duration"] {
            assert!(ONTOLOGY_SOURCE.contains(term), "missing ontology term: {term}");
        }
        for term in ["provision applicability", "precedence use_permission_conflict", "power one_extension", "unresolved map_boundary_interpretation"] {
            assert!(RULE_SOURCE.contains(term), "missing rule family: {term}");
        }
    }

    #[test]
    fn applicability_boundary() {
        assert!(chapter_applies(true, false));
        assert!(!chapter_applies(true, true));
        assert!(!chapter_applies(false, false));
    }

    #[test]
    fn precedence_rules() {
        assert_eq!(controlling_public_rule(true, false), RuleSet::Chapter50);
        assert_eq!(controlling_public_rule(false, false), RuleSet::External);
        assert_eq!(controlling_use_source(true), UseTableSource::ArticleEightToElevenList);
        assert_eq!(controlling_private_rule(true), RuleSet::Chapter50);
        assert_eq!(controlling_private_rule(false), RuleSet::PrivateAgreement);
    }

    #[test]
    fn transitional_state_rules() {
        assert!(old_violation_continues(false));
        assert!(!old_violation_continues(true));
        assert!(prior_nonconformity_continues(true, true, false));
        assert!(!prior_nonconformity_continues(true, true, true));
        assert!(may_extend_prior_approval(true, true, 0, 12));
        assert!(!may_extend_prior_approval(true, true, 1, 12));
        assert!(!may_extend_prior_approval(true, true, 0, 13));
        assert!(may_choose_prior_rules(true, true, true));
        assert!(!may_choose_prior_rules(true, false, true));
    }
}
