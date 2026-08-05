/**
 * The quantity choropleths published so far.
 *
 * Band edges, labels, and colours mirror `BANDS` in
 * assessed-value-per-acre/build_assessed_value_asset.py. The keys `b0`…`b5` are
 * assigned there from the same list, so the two stay in step by position.
 */

import type { QuantityMapConfig } from "./quantity";

export const ASSESSED_VALUE_PER_ACRE: QuantityMapConfig = {
  slug: "assessed-value-per-acre",
  title: "Detroit’s assessed property value per acre",
  subtitle:
    "Total assessed land and improvement value divided by recorded parcel area",
  kicker: "LAND VALUE · ALL PARCELS · CITY OF DETROIT",
  standfirst:
    "Assessed value per acre makes parcels of different sizes directly " +
    "comparable. Select any parcel to see its own value.",
  navLabel: "Value per acre",
  bandField: "band_av",
  measureField: "vpa",
  measureLabel: "Assessed value per acre",
  absentLabel: "No recorded value / $0",
  bands: [
    { key: "b0", label: "$1–$25,000", color: "#a7c6ed" },
    { key: "b1", label: "$25,001–$100,000", color: "#5790db" },
    { key: "b2", label: "$100,001–$250,000", color: "#ffb549" },
    { key: "b3", label: "$250,001–$500,000", color: "#e8783d" },
    { key: "b4", label: "$500,001–$1 million", color: "#c83a3a" },
    { key: "b5", label: "More than $1 million", color: "#8f1d2d" },
  ],
  metricLabel: [
    "OF ASSESSED VALUE IS CONCENTRATED",
    "ON 10% OF RECORDED PARCEL ACREAGE",
  ],
  metricNote: [
    "Assessed value per acre makes parcels of",
    "different sizes directly comparable.",
  ],
  aside: {
    title: "What this measures",
    lines: [
      "The assessment includes both land and",
      "buildings. It is not a land-only value,",
      "sale price, tax bill, or taxable value.",
    ],
  },
  // Seven entries will not fit on one line at board width; the printed exhibit
  // wraps them at these positions rather than shrinking the type.
  legendRows: [
    [67, 330, 585, 865],
    [67, 350, 655],
  ],
  sources: [
    "Source: City of Detroit parcel assessment data downloaded in 2026.",
    "Values are nominal assessor records and have not been adjusted for exemptions or assessment-year differences.",
  ],
};

export const QUANTITY_MAPS = {
  assessed_value_per_acre: ASSESSED_VALUE_PER_ACRE,
};
