//! Civil-time values and explicit calendar policies.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Stable identity of the calendar used by a legal temporal operation.
#[derive(Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
#[serde(transparent)]
pub struct CalendarPolicyId(pub String);

/// Exact civil date without an implied timezone or business calendar.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
pub struct CivilDate {
    /// Proleptic calendar year.
    pub year: i32,
    /// One-based calendar month.
    pub month: u8,
    /// One-based day of month.
    pub day: u8,
}

impl CivilDate {
    /// Creates a structurally valid civil date.
    ///
    /// Month-length and leap-year validation belongs to the selected calendar
    /// implementation rather than this transport value.
    ///
    /// # Errors
    ///
    /// Returns an error when month or day lies outside its structural range.
    pub fn new(year: i32, month: u8, day: u8) -> Result<Self, TemporalError> {
        if !(1..=12).contains(&month) || !(1..=31).contains(&day) {
            return Err(TemporalError::InvalidCivilDate);
        }
        Ok(Self { year, month, day })
    }
}

/// Exact local wall-clock time, independent of timezone resolution.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
pub struct LocalTime {
    /// Hour from zero through 23.
    pub hour: u8,
    /// Minute from zero through 59.
    pub minute: u8,
    /// Second from zero through 59.
    pub second: u8,
}

impl LocalTime {
    /// Creates a structurally valid local wall-clock time.
    ///
    /// # Errors
    ///
    /// Returns an error when any field is outside its clock range.
    pub fn new(hour: u8, minute: u8, second: u8) -> Result<Self, TemporalError> {
        if hour > 23 || minute > 59 || second > 59 {
            return Err(TemporalError::InvalidLocalTime);
        }
        Ok(Self {
            hour,
            minute,
            second,
        })
    }
}

/// Local date and time whose legal interpretation requires a named timezone.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize, Deserialize)]
pub struct LocalDateTime {
    /// Civil date component.
    pub date: CivilDate,
    /// Wall-clock component.
    pub time: LocalTime,
}

/// A legal calendar operation that cannot execute without a policy provider.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "unit")]
pub enum CalendarOffset {
    /// A count of calendar months under a named end-of-month policy.
    CalendarMonths {
        /// Signed number of months.
        count: i32,
        /// Calendar implementation required to resolve the offset.
        policy: CalendarPolicyId,
    },
    /// A count of business days under a named holiday/closure policy.
    BusinessDays {
        /// Signed number of business days.
        count: i32,
        /// Calendar implementation required to resolve the offset.
        policy: CalendarPolicyId,
    },
}

#[derive(Clone, Copy, Debug, Error, Eq, PartialEq)]
/// Invalid structural civil-time value.
pub enum TemporalError {
    /// Month or day is outside its structural range.
    #[error("civil date fields are outside their structural ranges")]
    InvalidCivilDate,
    /// Clock component is outside its structural range.
    #[error("local time fields are outside their structural ranges")]
    InvalidLocalTime,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn policy_is_part_of_calendar_offset_identity() {
        let city = CalendarOffset::BusinessDays {
            count: 3,
            policy: CalendarPolicyId("detroit_business_calendar".into()),
        };
        let federal = CalendarOffset::BusinessDays {
            count: 3,
            policy: CalendarPolicyId("federal_business_calendar".into()),
        };
        assert_ne!(city, federal);
    }

    #[test]
    fn validates_structural_date_and_time_fields() {
        assert!(CivilDate::new(2026, 7, 31).is_ok());
        assert_eq!(
            CivilDate::new(2026, 13, 1),
            Err(TemporalError::InvalidCivilDate)
        );
        assert!(LocalTime::new(16, 0, 0).is_ok());
        assert_eq!(
            LocalTime::new(24, 0, 0),
            Err(TemporalError::InvalidLocalTime)
        );
    }
}
