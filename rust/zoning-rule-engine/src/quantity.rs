//! Exact, dimensionally typed quantities used by zoning rules.
//!
//! Length uses the same integer lattice as the Belle Isle/Bonsai extension:
//! one lattice unit is 1/32,000,000 metre. Both metric millimetres and imperial
//! fractions through 1/256 inch therefore have integral representations.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Exact length lattice units per metre.
pub const LENGTH_UNITS_PER_METER: i128 = 32_000_000;
/// Exact length lattice units per millimetre.
pub const LENGTH_UNITS_PER_MILLIMETER: i128 = 32_000;
/// Exact length lattice units per inch (`1 inch = 127/5000 metre`).
pub const LENGTH_UNITS_PER_INCH: i128 = 812_800;
/// Exact length lattice units per foot.
pub const LENGTH_UNITS_PER_FOOT: i128 = 9_753_600;
/// Exact length lattice units per 1/256 inch.
pub const LENGTH_UNITS_PER_256TH_INCH: i128 = 3_175;

mod decimal_i128 {
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(value: &i128, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&value.to_string())
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<i128, D::Error>
    where
        D: Deserializer<'de>,
    {
        let value = String::deserialize(deserializer)?;
        value.parse().map_err(serde::de::Error::custom)
    }
}

mod decimal_i64 {
    use serde::{Deserialize, Deserializer, Serializer};

    #[allow(clippy::trivially_copy_pass_by_ref)]
    pub fn serialize<S>(value: &i64, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&value.to_string())
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<i64, D::Error>
    where
        D: Deserializer<'de>,
    {
        let value = String::deserialize(deserializer)?;
        value.parse().map_err(serde::de::Error::custom)
    }
}

/// An invalid exact quantity construction.
#[derive(Clone, Copy, Debug, Error, Eq, PartialEq)]
pub enum QuantityError {
    /// A rational quantity cannot have a zero denominator.
    #[error("quantity denominator cannot be zero")]
    ZeroDenominator,
    /// The requested value does not land exactly on the internal lattice.
    #[error("quantity is not exactly representable on the internal lattice")]
    OffLattice,
}

/// A legal length stored as an exact count of 1/32,000,000 metre units.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(transparent)]
pub struct Length(#[serde(with = "decimal_i128")] i128);

impl Length {
    /// Constructs an integral number of feet exactly.
    #[must_use]
    pub const fn feet(value: i128) -> Self {
        Self(value * LENGTH_UNITS_PER_FOOT)
    }

    /// Constructs an integral number of inches exactly.
    #[must_use]
    pub const fn inches(value: i128) -> Self {
        Self(value * LENGTH_UNITS_PER_INCH)
    }

    /// Constructs an integral number of metres exactly.
    #[must_use]
    pub const fn meters(value: i128) -> Self {
        Self(value * LENGTH_UNITS_PER_METER)
    }

    /// Constructs an integral number of millimetres exactly.
    #[must_use]
    pub const fn millimeters(value: i128) -> Self {
        Self(value * LENGTH_UNITS_PER_MILLIMETER)
    }

    /// Constructs a rational number of inches when it lies on the lattice.
    ///
    /// # Errors
    ///
    /// Returns [`QuantityError::ZeroDenominator`] for a zero denominator and
    /// [`QuantityError::OffLattice`] when rounding would be required.
    pub fn fractional_inches(numerator: i128, denominator: i128) -> Result<Self, QuantityError> {
        exact_ratio(numerator * LENGTH_UNITS_PER_INCH, denominator).map(Self)
    }

    /// Returns the exact internal lattice count.
    #[must_use]
    pub const fn lattice_units(self) -> i128 {
        self.0
    }

    /// Returns an exact `(numerator, denominator)` representation in feet.
    #[must_use]
    pub const fn as_feet_ratio(self) -> (i128, i128) {
        (self.0, LENGTH_UNITS_PER_FOOT)
    }
}

/// A legal area stored as exact squared length-lattice units.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(transparent)]
pub struct Area(#[serde(with = "decimal_i128")] i128);

impl Area {
    /// Constructs an integral number of square feet exactly.
    #[must_use]
    pub const fn square_feet(value: i128) -> Self {
        Self(value * LENGTH_UNITS_PER_FOOT * LENGTH_UNITS_PER_FOOT)
    }

    /// Constructs an integral number of square metres exactly.
    #[must_use]
    pub const fn square_meters(value: i128) -> Self {
        Self(value * LENGTH_UNITS_PER_METER * LENGTH_UNITS_PER_METER)
    }

    /// Returns the exact internal squared-lattice count.
    #[must_use]
    pub const fn square_lattice_units(self) -> i128 {
        self.0
    }

    /// Returns an exact `(numerator, denominator)` representation in square feet.
    #[must_use]
    pub const fn as_square_feet_ratio(self) -> (i128, i128) {
        (self.0, LENGTH_UNITS_PER_FOOT * LENGTH_UNITS_PER_FOOT)
    }
}

impl std::ops::Mul<Length> for Length {
    type Output = Area;

    fn mul(self, rhs: Length) -> Self::Output {
        Area(
            self.0
                .checked_mul(rhs.0)
                .expect("length multiplication exceeds the supported legal area domain"),
        )
    }
}

/// A reduced, exact dimensionless ratio, such as lot coverage.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
pub struct Ratio {
    #[serde(with = "decimal_i64")]
    numerator: i64,
    #[serde(with = "decimal_i64")]
    denominator: i64,
}

impl Ratio {
    /// Constructs an integral percentage exactly.
    #[must_use]
    pub fn percent(value: i64) -> Self {
        let divisor = gcd_i64(value, 100);
        Self {
            numerator: value / divisor,
            denominator: 100 / divisor,
        }
    }

    /// Constructs a rational ratio and reduces it to canonical form.
    ///
    /// # Errors
    ///
    /// Returns [`QuantityError::ZeroDenominator`] for a zero denominator.
    pub fn new(numerator: i64, denominator: i64) -> Result<Self, QuantityError> {
        if denominator == 0 {
            return Err(QuantityError::ZeroDenominator);
        }
        let sign = if denominator < 0 { -1 } else { 1 };
        let divisor = gcd_i64(numerator, denominator);
        Ok(Self {
            numerator: sign * numerator / divisor,
            denominator: sign * denominator / divisor,
        })
    }

    /// Returns the reduced numerator and denominator.
    #[must_use]
    pub const fn parts(self) -> (i64, i64) {
        (self.numerator, self.denominator)
    }
}

impl<'de> Deserialize<'de> for Ratio {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        #[derive(Deserialize)]
        struct UncheckedRatio {
            #[serde(with = "decimal_i64")]
            numerator: i64,
            #[serde(with = "decimal_i64")]
            denominator: i64,
        }

        let unchecked = UncheckedRatio::deserialize(deserializer)?;
        Self::new(unchecked.numerator, unchecked.denominator).map_err(serde::de::Error::custom)
    }
}

impl PartialOrd for Ratio {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Ratio {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        (i128::from(self.numerator) * i128::from(other.denominator))
            .cmp(&(i128::from(other.numerator) * i128::from(self.denominator)))
    }
}

/// How an exact rational threshold applies to a whole-number count.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "comparison")]
pub enum WholeCountThreshold {
    /// Count must be at least the rational share, rounded upward.
    AtLeast {
        /// Exact nonnegative share of the population.
        share: Ratio,
    },
    /// Count must be strictly greater than the rational share.
    MoreThan {
        /// Exact nonnegative share of the population.
        share: Ratio,
    },
}

impl WholeCountThreshold {
    /// Returns the least whole count satisfying this threshold.
    ///
    /// # Panics
    ///
    /// Panics if the share is negative or if the resulting count exceeds the
    /// supported `u64` population domain.
    #[must_use]
    pub fn required(self, population: u64) -> u64 {
        let share = match self {
            Self::AtLeast { share } | Self::MoreThan { share } => share,
        };
        let (numerator, denominator) = share.parts();
        assert!(
            numerator >= 0 && denominator > 0,
            "count shares must be nonnegative"
        );
        let product = u128::from(population) * u128::from(numerator.unsigned_abs());
        let divisor = u128::from(denominator.unsigned_abs());
        let value = match self {
            Self::AtLeast { .. } => product.div_ceil(divisor),
            Self::MoreThan { .. } => product / divisor + 1,
        };
        u64::try_from(value).expect("required count exceeds u64")
    }
}

/// A legal duration stored as an exact integral number of seconds.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(transparent)]
pub struct Duration(#[serde(with = "decimal_i128")] i128);

impl Duration {
    /// Constructs an integral number of 24-hour days exactly.
    #[must_use]
    pub const fn days(value: i128) -> Self {
        Self(value * 86_400)
    }

    /// Constructs an integral number of seconds exactly.
    #[must_use]
    pub const fn seconds(value: i128) -> Self {
        Self(value)
    }

    /// Returns the exact number of seconds.
    #[must_use]
    pub const fn as_seconds(self) -> i128 {
        self.0
    }
}

fn exact_ratio(numerator: i128, denominator: i128) -> Result<i128, QuantityError> {
    if denominator == 0 {
        return Err(QuantityError::ZeroDenominator);
    }
    if numerator % denominator != 0 {
        return Err(QuantityError::OffLattice);
    }
    Ok(numerator / denominator)
}

fn gcd_i64(mut left: i64, mut right: i64) -> i64 {
    left = left.abs();
    right = right.abs();
    while right != 0 {
        (left, right) = (right, left % right);
    }
    left.max(1)
}

#[cfg(test)]
mod tests {
    use super::{
        Area, Duration, LENGTH_UNITS_PER_256TH_INCH, LENGTH_UNITS_PER_FOOT, LENGTH_UNITS_PER_INCH,
        LENGTH_UNITS_PER_METER, Length, QuantityError, Ratio, WholeCountThreshold,
    };

    #[test]
    fn lattice_matches_belle_isle_exactly() {
        assert_eq!(LENGTH_UNITS_PER_METER, 32_000_000);
        assert_eq!(LENGTH_UNITS_PER_INCH, 812_800);
        assert_eq!(LENGTH_UNITS_PER_FOOT, 9_753_600);
        assert_eq!(LENGTH_UNITS_PER_256TH_INCH, 3_175);
        assert_eq!(
            Length::fractional_inches(1, 256).unwrap().lattice_units(),
            3_175
        );
    }

    #[test]
    fn derives_area_from_two_lengths_exactly() {
        let area = Length::feet(50) * Length::feet(100);
        assert_eq!(area, Area::square_feet(5_000));
        assert_eq!(
            area.as_square_feet_ratio().0,
            5_000 * area.as_square_feet_ratio().1
        );
    }

    #[test]
    fn represents_legal_values_without_floats() {
        assert_eq!(Ratio::percent(35).parts(), (7, 20));
        assert_eq!(Duration::days(15).as_seconds(), 1_296_000);
        assert_eq!(
            Length::fractional_inches(1, 512),
            Err(QuantityError::OffLattice)
        );
    }

    #[test]
    fn json_round_trip_preserves_exact_boundary_values() {
        let boundary = Area::square_feet(5_000);
        let payload = serde_json::to_string(&boundary).unwrap();
        assert!(payload.starts_with('"'));
        let restored: Area = serde_json::from_str(&payload).unwrap();
        assert_eq!(restored, boundary);
    }

    #[test]
    fn exact_vote_thresholds_define_rounding() {
        let majority = WholeCountThreshold::MoreThan {
            share: Ratio::new(1, 2).unwrap(),
        };
        let two_thirds = WholeCountThreshold::AtLeast {
            share: Ratio::new(2, 3).unwrap(),
        };
        assert_eq!(majority.required(9), 5);
        assert_eq!(two_thirds.required(9), 6);
        assert_eq!(majority.required(8), 5);
        assert_eq!(two_thirds.required(8), 6);
    }
}
