/**
 * Parcel dimensional standards, as configuration.
 *
 * Every rule in this family — minimum lot area, minimum lot width, and the
 * setback and coverage rules to come — is the same map: 378,366 parcels in one
 * shared archive, classified into four states by a test Python already owns,
 * over one column per rule. So a rule is a config object, and the spec, the
 * explorer, and the frozen board are written once.
 */

import { brand, dataColor } from "../../tokens";
import type { LegendEntry, MapMetric, MapSpec } from "../types";

const DISPLAY_TILES = "/data/zoning/parcels-display.pmtiles";
const LOOKUP_TILES = "/data/zoning/parcels.pmtiles";

/** Detroit's parcel extent, as reported by the archive header. */
const BOUNDS: [number, number, number, number] = [
  -83.287694, 42.255387, -82.910539, 42.450244,
];

/** Emitted per rule by scripts/build_parcel_tiles.py. */
export type ParcelRuleSummary = {
  /**
   * Null where the standard is not a single number. The setback envelope is a
   * composite of front, rear, and side yards that varies by district and lot
   * geometry, so there is no one threshold to report — and inventing one would
   * misdescribe the rule.
   */
  legalMinimum: number | null;
  screeningBoundary: number | null;
  unit: "square_feet" | "feet";
  evaluatedParcels: number;
  belowMinimumParcels: number;
  meetsMinimumParcels: number;
  belowMinimumShare: number;
  unknownParcels: number;
  outsideScopeParcels: number;
  parksParcels: number;
  totalParcels: number;
  bzaCases: number;
  bzaGrantedOrReversed: number;
};

export type ParcelRuleConfig = {
  slug: string;
  title: string;
  subtitle: string;
  /** Eyebrow shown above the heading on the interactive route. */
  kicker: string;
  standfirst: string;
  /** Short nav label. Explicit, not derived — deriving it from measureLabel
      produced "Lot lot area". */
  navLabel: string;
  /** Tile column holding this rule's status: `st_area`, `st_width`, … */
  statusField: string;
  /** Tile column holding the measured value. */
  measureField: string;
  measureLabel: string;
  /** Uppercase label under the headline figure; one entry per line. */
  metricLabel: string[];
  /** Sentences under the metric. Each rule qualifies its result differently. */
  metricNote: string[];
  /** Wording for the four states in the reconciliation line. */
  stateLabels: { below: string; meets: string; unknown: string; outside: string };
  /** Leading words of the reconciliation line, e.g. "Parcel result". */
  accountingLead: string;
  /**
   * Legend wording for the three painted states. All three vary: the lot rules
   * describe what relief a proposal would need, the setback rule describes an
   * existing building's relationship to its required yards.
   */
  failsLabel: string;
  meetsLabel: string;
  absentLabel: string;
  failsNote: string;
  meetsNote: string;
  /** Noun used in the BZA aside: "lot-area", "lot-width". */
  bzaLabel: string;
  bzaHistoryLabel: string;
  /** Method line, before the generated parcel accounting. */
  methodLine: string;
  /** Trailing sources line. */
  sourcesLine: string;
};

/**
 * The four states, matching the project's language boundary: a geometric
 * failure is "would require relief under today's standard", never "illegal".
 */
export function ruleLegend(config: ParcelRuleConfig): LegendEntry[] {
  return [
    {
      label: config.failsLabel,
      color: dataColor.fails,
      note: config.failsNote,
    },
    {
      label: config.meetsLabel,
      color: dataColor.meets,
      note: config.meetsNote,
    },
    {
      label: config.absentLabel,
      color: dataColor.absent,
      note: "no value recorded, or the rule does not apply",
    },
  ];
}

export function parcelRuleSpec(config: ParcelRuleConfig): MapSpec {
  return {
    id: config.slug,
    title: config.title,
    subtitle: config.subtitle,
    view: { longitude: -83.1, latitude: 42.353, zoom: 10.4 },
    // 10.5 is the complete-city framing floor. Closer camera views overscale
    // the high-detail z10 display tiles; z15 remains lookup-only.
    minZoom: 10.5,
    displayTileZoom: 10,
    bounds: BOUNDS,
    fitPadding: 0,
    layers: [
      {
        id: "parcels",
        label: "Parcels",
        source: { kind: "pmtiles", url: DISPLAY_TILES, sourceLayer: "parcels" },
        geometry: "polygon",
        pickable: true,
        fill: {
          kind: "categorical",
          field: config.statusField,
          palette: {
            below: dataColor.fails,
            meets: dataColor.meets,
            // Distinct in the data, deliberately identical on the map: the
            // reader is told "not evaluated", not "compliant".
            unknown: dataColor.absent,
            outside: dataColor.absent,
          },
          fallback: dataColor.absent,
          // Matches the painting order of the printed exhibit: context first,
          // then compliant, then the consequential state on top.
          drawOrder: ["outside", "unknown", "meets", "below"],
        },
      },
      {
        id: "roads",
        label: "Major roads",
        source: { kind: "pmtiles", url: DISPLAY_TILES, sourceLayer: "roads" },
        geometry: "line",
        // road_context has only 29 features but they are MultiLineStrings
        // covering the whole arterial grid, so this layer carries far more ink
        // than the feature count suggests. The printed exhibit draws it at
        // 0.22pt / 36% alpha; deck.gl still paints roughly a pixel for any
        // sub-pixel line, so the weight has to come out of the opacity.
        opacity: 0.22,
        stroke: { color: { kind: "constant", color: brand.navy }, widthPx: 0.4 },
      },
    ],
    legend: ruleLegend(config),
    inspect: {
      layerId: "parcels",
      idField: "pid",
      titleField: "addr",
      fields: [
        { field: "pid", label: "Parcel ID", format: "text" },
        { field: "zd", label: "Zoning district", format: "text" },
        {
          field: config.measureField,
          label: config.measureLabel,
          format: config.measureField === "sqft" ? "sqft" : "feet",
        },
        { field: config.statusField, label: "Status", format: "status" },
      ],
      lookupSource: {
        kind: "pmtiles",
        url: LOOKUP_TILES,
        sourceLayer: "parcels",
      },
      lookupZoom: 15,
    },
    sources: [config.methodLine, config.sourcesLine],
  };
}

export const STATUS_LABELS: Record<string, string> = {
  below: "Would require relief under today's standard",
  meets: "Meets the minimum as measured",
  unknown: "Not enough information to evaluate",
  outside: "Outside R1–R6, or the rule does not apply",
};

export function ruleMetric(
  config: ParcelRuleConfig,
  summary: ParcelRuleSummary,
  detailNoun = "evaluated parcels",
): MapMetric {
  return {
    value: `${Math.round(summary.belowMinimumShare * 100)}%`,
    label: config.metricLabel,
    detail: `${summary.belowMinimumParcels.toLocaleString()} of ${summary.evaluatedParcels.toLocaleString()} ${detailNoun}`,
    note: config.metricNote,
  };
}

/**
 * The reconciliation line, so every parcel is visibly accounted for.
 *
 * Counts come from `parcel-rules.json`, which the tile builder derives from the
 * same status series it paints — the summary and the map cannot disagree.
 */
export function ruleAccounting(
  config: ParcelRuleConfig,
  summary: ParcelRuleSummary,
): string {
  const { stateLabels: s } = config;
  const parts = [
    `${summary.belowMinimumParcels.toLocaleString()} ${s.below}`,
    `${summary.meetsMinimumParcels.toLocaleString()} ${s.meets}`,
    `${summary.unknownParcels.toLocaleString()} ${s.unknown}`,
  ];
  if (summary.parksParcels > 0) {
    parts.push(
      `${summary.parksParcels.toLocaleString()} Parks & Recreation taxpayer`,
    );
  }
  parts.push(`${summary.outsideScopeParcels.toLocaleString()} ${s.outside}`);
  return `${config.accountingLead}: ${parts.join(" · ")}.`;
}

/**
 * A recorded 0 is an absent measurement, not a zero-size lot — and it is
 * exactly the case the classifier routes to "not enough information". Printing
 * "0 sq. ft." would present missing evidence as a finding.
 */
export function formatMeasure(
  value: unknown,
  format: string | undefined,
): string {
  if (value == null || value === "") return "Not recorded";
  if (format === "status") return STATUS_LABELS[String(value)] ?? String(value);
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return "Not recorded";
  if (format === "sqft") return `${n.toLocaleString()} sq. ft.`;
  if (format === "feet") return `${n.toLocaleString()} ft.`;
  if (format === "currency") return `$${n.toLocaleString()}`;
  return String(value);
}
