//! Refinement predicates and proof-bearing values.
//!
//! A legal constraint denotes a set of admissible values. The base value type
//! still carries its physical dimension and legal role; predicates refine that
//! type through intervals, equality, union, intersection, and complement.

use serde::{Deserialize, Deserializer, Serialize};
use thiserror::Error;

/// One endpoint of an interval.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "kind", content = "value")]
pub enum Bound<T> {
    /// The endpoint belongs to the interval.
    Included(T),
    /// The endpoint does not belong to the interval.
    Excluded(T),
    /// The interval has no endpoint in this direction.
    Unbounded,
}

impl<T> Bound<T> {
    fn value(&self) -> Option<&T> {
        match self {
            Self::Included(value) | Self::Excluded(value) => Some(value),
            Self::Unbounded => None,
        }
    }
}

/// A validated interval with independently open, closed, or unbounded ends.
#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct Interval<T> {
    lower: Bound<T>,
    upper: Bound<T>,
}

impl<'de, T> Deserialize<'de> for Interval<T>
where
    T: Deserialize<'de> + PartialOrd,
{
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        #[derive(Deserialize)]
        struct UncheckedInterval<T> {
            lower: Bound<T>,
            upper: Bound<T>,
        }

        let unchecked = UncheckedInterval::deserialize(deserializer)?;
        Self::new(unchecked.lower, unchecked.upper).map_err(serde::de::Error::custom)
    }
}

impl<T: PartialOrd> Interval<T> {
    /// Constructs a nonempty, ordered interval.
    ///
    /// # Errors
    ///
    /// Returns [`RefinementError::InvertedInterval`] when the lower endpoint is
    /// greater than the upper endpoint. Returns
    /// [`RefinementError::EmptyInterval`] when equal endpoints exclude either
    /// side. An incomparable endpoint produces
    /// [`RefinementError::IncomparableBounds`].
    pub fn new(lower: Bound<T>, upper: Bound<T>) -> Result<Self, RefinementError> {
        if let (Some(low), Some(high)) = (lower.value(), upper.value()) {
            match low.partial_cmp(high) {
                Some(std::cmp::Ordering::Greater) => {
                    return Err(RefinementError::InvertedInterval);
                }
                Some(std::cmp::Ordering::Equal)
                    if !matches!(&lower, Bound::Included(_))
                        || !matches!(&upper, Bound::Included(_)) =>
                {
                    return Err(RefinementError::EmptyInterval);
                }
                None => return Err(RefinementError::IncomparableBounds),
                _ => {}
            }
        }
        Ok(Self { lower, upper })
    }

    /// Returns the lower endpoint.
    #[must_use]
    pub const fn lower(&self) -> &Bound<T> {
        &self.lower
    }

    /// Returns the upper endpoint.
    #[must_use]
    pub const fn upper(&self) -> &Bound<T> {
        &self.upper
    }

    /// Tests membership in the interval.
    #[must_use]
    pub fn contains(&self, candidate: &T) -> bool {
        let above_lower = match &self.lower {
            Bound::Included(lower) => candidate >= lower,
            Bound::Excluded(lower) => candidate > lower,
            Bound::Unbounded => true,
        };
        let below_upper = match &self.upper {
            Bound::Included(upper) => candidate <= upper,
            Bound::Excluded(upper) => candidate < upper,
            Bound::Unbounded => true,
        };
        above_lower && below_upper
    }
}

/// A composable, serializable legal constraint over values of one type.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "operator", content = "arguments")]
#[serde(bound(deserialize = "T: Deserialize<'de> + PartialOrd"))]
pub enum Constraint<T> {
    /// Membership in one interval.
    Interval(Interval<T>),
    /// Equality with one value.
    Equal(T),
    /// Membership in a finite set.
    OneOf(Vec<T>),
    /// Logical conjunction / set intersection.
    All(Vec<Self>),
    /// Logical disjunction / set union.
    Any(Vec<Self>),
    /// Logical negation / set complement.
    Not(Box<Self>),
}

/// A predicate that can refine values of type `T`.
pub trait Predicate<T> {
    /// Returns whether `candidate` satisfies the predicate.
    fn test(&self, candidate: &T) -> bool;
}

impl<T: PartialEq + PartialOrd> Predicate<T> for Constraint<T> {
    fn test(&self, candidate: &T) -> bool {
        match self {
            Self::Interval(interval) => interval.contains(candidate),
            Self::Equal(value) => candidate == value,
            Self::OneOf(values) => values.contains(candidate),
            Self::All(predicates) => predicates.iter().all(|value| value.test(candidate)),
            Self::Any(predicates) => predicates.iter().any(|value| value.test(candidate)),
            Self::Not(predicate) => !predicate.test(candidate),
        }
    }
}

/// A value accompanied by the predicate it has been proven to satisfy.
///
/// Fields are private so callers cannot manufacture a proof without running
/// the predicate. Deserialization is intentionally absent for the same reason:
/// serialized claims must be re-verified at a trust boundary.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Refined<T, P> {
    value: T,
    predicate: P,
}

impl<T, P: Predicate<T>> Refined<T, P> {
    /// Verifies `value` and returns a proof-bearing wrapper.
    ///
    /// # Errors
    ///
    /// Returns [`RefinementError::PredicateNotSatisfied`] when the predicate
    /// rejects the value.
    pub fn verify(value: T, predicate: P) -> Result<Self, RefinementError> {
        if predicate.test(&value) {
            Ok(Self { value, predicate })
        } else {
            Err(RefinementError::PredicateNotSatisfied)
        }
    }

    /// Returns the verified value.
    #[must_use]
    pub const fn value(&self) -> &T {
        &self.value
    }

    /// Returns the predicate that constitutes the proof.
    #[must_use]
    pub const fn predicate(&self) -> &P {
        &self.predicate
    }

    /// Consumes the proof and returns its value.
    #[must_use]
    pub fn into_inner(self) -> T {
        self.value
    }
}

/// A malformed interval or failed refinement.
#[derive(Clone, Copy, Debug, Error, Eq, PartialEq)]
pub enum RefinementError {
    /// Lower endpoint is greater than the upper endpoint.
    #[error("interval lower bound exceeds its upper bound")]
    InvertedInterval,
    /// Equal endpoints exclude at least one side, producing an empty set.
    #[error("interval is empty")]
    EmptyInterval,
    /// Endpoints cannot be ordered, for example because one is NaN.
    #[error("interval endpoints are incomparable")]
    IncomparableBounds,
    /// A candidate is outside the set denoted by its predicate.
    #[error("value does not satisfy its refinement predicate")]
    PredicateNotSatisfied,
}

#[cfg(test)]
mod tests {
    use super::{Bound, Constraint, Interval, Predicate, Refined, RefinementError};
    use crate::{Area, Length};

    fn minimum_lot_area() -> Constraint<Area> {
        Constraint::Interval(
            Interval::new(Bound::Included(Area::square_feet(5_000)), Bound::Unbounded)
                .expect("the statutory interval is valid"),
        )
    }

    #[test]
    fn distinguishes_included_and_excluded_endpoints() {
        let closed = Interval::new(Bound::Included(1), Bound::Included(10)).unwrap();
        let open = Interval::new(Bound::Excluded(1), Bound::Excluded(10)).unwrap();
        assert!(closed.contains(&1));
        assert!(closed.contains(&10));
        assert!(!open.contains(&1));
        assert!(!open.contains(&10));
    }

    #[test]
    fn rejects_empty_or_inverted_intervals() {
        assert_eq!(
            Interval::new(Bound::Included(10), Bound::Included(1)),
            Err(RefinementError::InvertedInterval)
        );
        assert_eq!(
            Interval::new(Bound::Included(5), Bound::Excluded(5)),
            Err(RefinementError::EmptyInterval)
        );
    }

    #[test]
    fn composes_set_operations() {
        let ordinary =
            Constraint::Interval(Interval::new(Bound::Included(1), Bound::Included(10)).unwrap());
        let exception = Constraint::Equal(5);
        let allowed = Constraint::All(vec![ordinary, Constraint::Not(Box::new(exception))]);
        assert!(allowed.test(&4));
        assert!(!allowed.test(&5));
    }

    #[test]
    fn creates_proof_only_for_satisfying_value() {
        let proof = Refined::verify(Area::square_feet(5_000), minimum_lot_area());
        assert!(proof.is_ok());
        let failure = Refined::verify(Area::square_feet(4_999), minimum_lot_area());
        assert_eq!(failure, Err(RefinementError::PredicateNotSatisfied));
    }

    #[test]
    fn predicate_type_preserves_physical_dimension() {
        let width = Constraint::Interval(
            Interval::new(Bound::Included(Length::feet(50)), Bound::Unbounded).unwrap(),
        );
        assert!(width.test(&Length::feet(50)));
        // `width.test(&Area::square_feet(5_000))` does not compile.
    }

    #[test]
    fn serialized_claims_do_not_deserialize_as_proofs() {
        let predicate = minimum_lot_area();
        let payload = serde_json::to_string(&predicate).unwrap();
        let restored: Constraint<Area> = serde_json::from_str(&payload).unwrap();
        assert!(restored.test(&Area::square_feet(5_000)));
        let proof = Refined::verify(Area::square_feet(5_000), restored);
        assert!(proof.is_ok());
    }

    #[test]
    fn deserialization_cannot_bypass_interval_validation() {
        let inverted = r#"{
            "lower":{"kind":"included","value":10},
            "upper":{"kind":"included","value":1}
        }"#;
        let restored = serde_json::from_str::<Interval<i32>>(inverted);
        assert!(restored.is_err());
    }
}
