/**
 * What a `ColorRule` means — in both dialects, in one file.
 *
 * The map is painted by MapLibre from a style expression; the same rule is also
 * evaluated in plain JS for picking, legends, and tests. Those were previously
 * in separate modules and drifted: the expression builder read the `threshold`
 * rule as MapLibre `step` (below the first edge → default) while the JS
 * resolver read it the other way round (below the first edge → first colour).
 * Nothing caught it because no published rule used a threshold yet.
 *
 * Keeping both here, adjacent, plus `paint.test.ts` asserting they agree over
 * the same inputs, is what stops that recurring.
 */

import type { ColorRule, LayerSpec } from "./types";

/** A MapLibre style expression. Deliberately loose — MapLibre validates it. */
export type StyleExpression = unknown;

/** Transparent, for a layer with no fill rule. */
const NONE = "rgba(0,0,0,0)";

export function colorExpression(rule: ColorRule | undefined): StyleExpression {
  if (!rule) return NONE;

  if (rule.kind === "constant") return rule.color;

  if (rule.kind === "categorical") {
    const pairs = Object.entries(rule.palette).flatMap(([value, color]) => [
      value,
      color,
    ]);
    // `to-string` so a numeric tile value still matches a string palette key.
    return [
      "match",
      ["to-string", ["get", rule.field]],
      ...pairs,
      rule.fallback,
    ];
  }

  const edges = rule.bins.flatMap((bin) => [bin.from, bin.color]);
  const step = [
    "step",
    ["to-number", ["get", rule.field]],
    rule.belowFirst,
    ...edges,
  ];
  // `to-number` turns a missing property into 0, which would silently colour an
  // unmeasured parcel as the lowest bin. Guard before stepping.
  return ["case", ["has", rule.field], step, rule.fallback];
}

/**
 * The same rule, evaluated against one feature's properties.
 *
 * Must agree with `colorExpression` for every input — see `paint.test.ts`.
 */
export function resolveColor(
  rule: ColorRule | undefined,
  properties: Record<string, unknown>,
): string | undefined {
  if (!rule) return undefined;
  if (rule.kind === "constant") return rule.color;

  const has = Object.prototype.hasOwnProperty.call(properties, rule.field);
  const raw = properties[rule.field];

  if (rule.kind === "categorical") {
    if (!has) return rule.fallback;
    return rule.palette[String(raw)] ?? rule.fallback;
  }

  if (!has) return rule.fallback;
  const value = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(value)) return rule.fallback;

  let color = rule.belowFirst;
  for (const bin of rule.bins) {
    if (value >= bin.from) color = bin.color;
    else break;
  }
  return color;
}

/**
 * `fill-sort-key` for a rule that declares a painting order.
 *
 * Assessor parcels overlap (condo splits, related parcels), so whichever is
 * drawn last wins those pixels. Left to tile order, "not evaluated" grey paints
 * over classified parcels and the map under-reports them.
 */
export function sortKey(layer: LayerSpec): StyleExpression | undefined {
  const fill = layer.fill;
  if (fill?.kind !== "categorical" || !fill.drawOrder?.length) return undefined;
  const pairs = fill.drawOrder.flatMap((value, index) => [value, index]);
  return ["match", ["to-string", ["get", fill.field]], ...pairs, -1];
}

/**
 * Rank used to break ties when several features contain the clicked point.
 *
 * Picking has to agree with painting: the inspector must name the parcel the
 * reader can see, which is the one `fill-sort-key` drew last.
 */
export function paintRank(
  layer: LayerSpec,
  properties: Record<string, unknown>,
): number {
  const fill = layer.fill;
  if (fill?.kind !== "categorical" || !fill.drawOrder?.length) return 0;
  const index = fill.drawOrder.indexOf(String(properties[fill.field]));
  return index === -1 ? -1 : index;
}
