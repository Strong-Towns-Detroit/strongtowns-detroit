/**
 * Banded quantity choropleths.
 *
 * The parcel dimensional standards ask a yes/no question and answer it in four
 * states. A quantity map does not: nothing passes or fails assessed value per
 * acre. It carries a band per parcel and reports a distribution statistic, so
 * it needs its own config shape rather than a strained reading of
 * `ParcelRuleConfig`.
 *
 * The binning itself happens in Python. The exhibit's bands are exclusive at
 * the lower edge and inclusive at the upper, which a MapLibre `step` expression
 * cannot express — `step` is inclusive-lower — and rounding the value to make
 * the edges line up would move parcels across bands. So the published
 * classifier assigns the band and the browser paints a category.
 */

import { brand, dataColor } from "../../tokens";
import type { LegendEntry, MapMetric, MapSpec } from "../types";

const DISPLAY_TILES = "/data/zoning/parcels-display.pmtiles";
const LOOKUP_TILES = "/data/zoning/parcels.pmtiles";

const BOUNDS: [number, number, number, number] = [
  -83.287694, 42.255387, -82.910539, 42.450244,
];

/** Emitted by the quantity pass in scripts/build_parcel_tiles.py. */
export type QuantitySummary = {
  totalParcels: number;
  recordedParcels: number;
  zeroAssessmentParcels: number;
  unrecordedParcels: number;
  topTenPercentLandValueShare: number;
};

export type QuantityBand = {
  /** Stable key written into the tiles: `b0`, `b1`, … */
  key: string;
  label: string;
  color: string;
};

export type QuantityMapConfig = {
  slug: string;
  title: string;
  subtitle: string;
  kicker: string;
  standfirst: string;
  navLabel: string;
  /** Tile column holding the band key. */
  bandField: string;
  /** Tile column holding the measured value. */
  measureField: string;
  measureLabel: string;
  /** Wording for parcels with no usable measurement. */
  absentLabel: string;
  bands: QuantityBand[];
  metricLabel: string[];
  metricNote: string[];
  /** Right-column explainer, in place of the BZA aside on the rule boards. */
  aside: { title: string; lines: string[] };
  /** Column positions per legend row on the frozen board. */
  legendRows: number[][];
  sources: string[];
};

export function quantityLegend(config: QuantityMapConfig): LegendEntry[] {
  return [
    // First, deliberately: an unmeasured parcel is not a low value, and the
    // reader meets that caveat before the ramp.
    { label: config.absentLabel, color: dataColor.absent },
    ...config.bands.map((band) => ({ label: band.label, color: band.color })),
  ];
}

export function quantitySpec(config: QuantityMapConfig): MapSpec {
  const palette: Record<string, string> = { none: dataColor.absent };
  for (const band of config.bands) palette[band.key] = band.color;

  return {
    id: config.slug,
    title: config.title,
    subtitle: config.subtitle,
    view: { longitude: -83.1, latitude: 42.353, zoom: 10.4 },
    bounds: BOUNDS,
    fitPadding: 0,
    minZoom: 10.5,
    displayTileZoom: 10,
    layers: [
      {
        id: "parcels",
        label: "Parcels",
        source: { kind: "pmtiles", url: DISPLAY_TILES, sourceLayer: "parcels" },
        geometry: "polygon",
        pickable: true,
        fill: {
          kind: "categorical",
          field: config.bandField,
          palette,
          fallback: dataColor.absent,
          // Highest band last, so the most concentrated value is not buried by
          // the low bands that surround it downtown.
          drawOrder: ["none", ...config.bands.map((band) => band.key)],
        },
      },
      {
        id: "roads",
        label: "Major roads",
        source: { kind: "pmtiles", url: DISPLAY_TILES, sourceLayer: "roads" },
        geometry: "line",
        opacity: 0.22,
        stroke: { color: { kind: "constant", color: brand.navy }, widthPx: 0.4 },
      },
    ],
    legend: quantityLegend(config),
    inspect: {
      layerId: "parcels",
      idField: "pid",
      titleField: "addr",
      fields: [
        { field: "pid", label: "Parcel ID", format: "text" },
        { field: "zd", label: "Zoning district", format: "text" },
        { field: config.measureField, label: config.measureLabel, format: "currency" },
      ],
      lookupSource: {
        kind: "pmtiles",
        url: LOOKUP_TILES,
        sourceLayer: "parcels",
      },
      lookupZoom: 15,
    },
    sources: config.sources,
  };
}

export function quantityMetric(
  config: QuantityMapConfig,
  summary: QuantitySummary,
): MapMetric {
  return {
    value: `${Math.round(summary.topTenPercentLandValueShare * 100)}%`,
    label: config.metricLabel,
    note: config.metricNote,
  };
}

/** Coverage line, so unmeasured parcels are visibly accounted for. */
export function quantityCoverage(summary: QuantitySummary): string {
  return (
    `Coverage: ${summary.recordedParcels.toLocaleString()} parcels with ` +
    `recorded area and assessment; ` +
    `${summary.zeroAssessmentParcels.toLocaleString()} have a recorded ` +
    `assessment of $0; ${summary.unrecordedParcels.toLocaleString()} lack a ` +
    `usable area or assessment.`
  );
}
