//! Identity-aware legal aggregation.

use std::collections::BTreeSet;

/// Counts unique entities satisfying a predicate. Values measured about those
/// entities are deliberately not used as the deduplication key.
pub fn count_distinct_by_identity<'a, T: 'a, Id: Ord + 'a>(
    values: impl IntoIterator<Item = &'a T>,
    identity: impl Fn(&T) -> Id,
    qualifies: impl Fn(&T) -> bool,
) -> usize {
    values
        .into_iter()
        .filter(|value| qualifies(value))
        .map(identity)
        .collect::<BTreeSet<_>>()
        .len()
}

#[cfg(test)]
mod tests {
    use super::count_distinct_by_identity;

    #[derive(Clone)]
    struct Site {
        id: u8,
        distance: u16,
    }

    #[test]
    fn deduplicates_entities_not_measurements() {
        let sites = [
            Site {
                id: 1,
                distance: 999,
            },
            Site {
                id: 2,
                distance: 999,
            },
            Site {
                id: 1,
                distance: 999,
            },
            Site {
                id: 3,
                distance: 1001,
            },
        ];
        assert_eq!(
            count_distinct_by_identity(&sites, |site| site.id, |site| site.distance <= 1000),
            2
        );
    }
}
