/**
 * The parcel dimensional standards published so far.
 *
 * Each entry is the whole publication. Porting the next canonical exhibit —
 * residential setback envelope, lot coverage, assessed value per acre — means
 * adding a classifier to scripts/build_parcel_tiles.py and an object here.
 */

import type { ParcelRuleConfig } from "./parcel-rule";

export const LOT_AREA: ParcelRuleConfig = {
  slug: "minimum-lot-area",
  title: "Detroit's 5,000-square-foot minimum lot area",
  subtitle:
    "Recorded R1–R6 parcel area compared with the 5,000-square-foot minimum",
  kicker: "PARCEL GEOMETRY · R1–R6 · CITY OF DETROIT",
  standfirst:
    "Every recorded residential parcel, measured against the minimum lot " +
    "area in force today. Select any parcel to see its own numbers.",
  navLabel: "Lot area",
  statusField: "st_area",
  measureField: "sqft",
  measureLabel: "Recorded lot area",
  metricLabel: ["BELOW THE 5,000-SQ.-FT. MINIMUM"],
  metricNote: [
    "Unless lot-of-record protection, a combined zoning lot, adjustment,",
    "variance, or another exception applies, new development cannot",
    "proceed under this minimum.",
  ],
  stateLabels: {
    below: "below",
    meets: "meet",
    unknown: "not enough data",
    outside: "outside R1\u2013R6",
  },
  accountingLead: "Parcel result",
  failsLabel: "Variance or exception required",
  meetsLabel: "Meets minimum area",
  absentLabel: "Not evaluated / outside R1\u2013R6",
  failsNote: "recorded area below 4,950 sq. ft.",
  meetsNote: "recorded area at or above the minimum",
  bzaLabel: "lot-area",
  bzaHistoryLabel: "residential minimum-lot-area",
  methodLine:
    "Classification: below minimum when recorded lot area is under 4,950 sq. ft.; the 1% tolerance avoids false precision around the legal 5,000-sq.-ft. boundary.",
  sourcesLine:
    "Sources: City parcel data; Detroit BZA minutes; Detroit Code §§50-13-1–7, 50-13-21.",
};

export const LOT_WIDTH: ParcelRuleConfig = {
  slug: "minimum-lot-width",
  title: "Detroit's 50-foot minimum residential lot width",
  subtitle:
    "Recorded R1–R6 frontage compared with the 50-foot minimum lot width",
  kicker: "PARCEL GEOMETRY · R1–R6 · CITY OF DETROIT",
  standfirst:
    "Every recorded residential parcel, measured against the minimum lot " +
    "width in force today. Select any parcel to see its own numbers.",
  navLabel: "Lot width",
  statusField: "st_width",
  measureField: "width",
  measureLabel: "Recorded frontage",
  metricLabel: ["BELOW THE 50-FT. MINIMUM"],
  metricNote: [
    "Unless lot-of-record protection, a combined zoning lot, adjustment,",
    "variance, or another exception applies, new development cannot",
    "proceed under this minimum.",
  ],
  stateLabels: {
    below: "below",
    meets: "meet",
    unknown: "not enough data",
    outside: "outside R1\u2013R6",
  },
  accountingLead: "Parcel result",
  failsLabel: "Variance or exception required",
  meetsLabel: "Meets minimum width",
  absentLabel: "Not evaluated / outside R1\u2013R6",
  failsNote: "recorded frontage below 49.5 ft.",
  meetsNote: "recorded frontage at or above the minimum",
  bzaLabel: "lot-width",
  bzaHistoryLabel: "residential minimum-lot-width",
  methodLine:
    "Classification: below minimum when recorded frontage is under 49.5 ft.; the 1% tolerance avoids false precision around the legal 50-ft. boundary.",
  // Carried over from the printed exhibit deliberately: frontage is a proxy,
  // and dropping the caveat would overstate what the map establishes.
  sourcesLine:
    "Frontage is a validated proxy, not a universal legal lot-width measurement. Sources: City parcel data; Detroit BZA minutes; Detroit Code §§50-13-1–7, 50-13-21.",
};

export const SETBACK_ENVELOPE: ParcelRuleConfig = {
  slug: "setback-envelope",
  title: "Detroit\u2019s single- and two-family setback envelope",
  subtitle:
    "Existing homes compared with Detroit\u2019s required front, rear, and side yards",
  kicker: "PARCEL GEOMETRY \u00b7 SINGLE- AND TWO-FAMILY \u00b7 CITY OF DETROIT",
  standfirst:
    "Every evaluated single- and two-family home, measured against the front, " +
    "rear, and side yards required today. Select any parcel to see its own numbers.",
  navLabel: "Setbacks",
  statusField: "st_setback",
  measureField: "outside_sqft",
  measureLabel: "Footprint outside envelope",
  metricLabel: [
    "OF PRINCIPAL BUILDING FOOTPRINTS VIOLATE",
    "ONE OR MORE SETBACK RULES",
  ],
  // This rule describes buildings that already exist, so its qualification is
  // about nonconformity rather than about what may be newly built.
  metricNote: [
    "Existing homes may remain as lawful nonconformities;",
    "additions or replacement construction can require setback relief.",
    "Accessory buildings follow different rules.",
  ],
  meetsLabel: "Within ordinary envelope",
  failsLabel: "Crosses ordinary envelope",
  absentLabel: "Not evaluated / other parcel type",
  failsNote: "footprint extends outside the required yards",
  meetsNote: "footprint sits within the required yards",
  stateLabels: {
    below: "cross",
    meets: "within",
    unknown: "not evaluated",
    outside: "other type",
  },
  accountingLead: "Result",
  bzaLabel: "setback",
  bzaHistoryLabel: "single- and two-family setback",
  methodLine:
    "Ordinary rectangular lots only; 11,070 sites without one clear principal building are not evaluated. Front edges use City Base Units street links.",
  sourcesLine:
    "Crossing requires more than 10 sq. ft. or 1% of the footprint outside both permissible side-yard allocations. Sources: City parcel data; City Base Units; Detroit BZA minutes.",
};

export const PARCEL_RULES = {
  lot_area: LOT_AREA,
  lot_width: LOT_WIDTH,
  setback_envelope: SETBACK_ENVELOPE,
};
export type ParcelRuleKey = keyof typeof PARCEL_RULES;

/** Resolve a URL slug to its config and the key it uses in parcel-rules.json. */
export function ruleBySlug(
  slug: string,
): { key: ParcelRuleKey; config: ParcelRuleConfig } | undefined {
  const entry = (Object.entries(PARCEL_RULES) as [
    ParcelRuleKey,
    ParcelRuleConfig,
  ][]).find(([, config]) => config.slug === slug);
  return entry ? { key: entry[0], config: entry[1] } : undefined;
}

export const RULE_SLUGS = Object.values(PARCEL_RULES).map((r) => r.slug);
