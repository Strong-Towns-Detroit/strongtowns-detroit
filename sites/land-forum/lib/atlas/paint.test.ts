/**
 * The two readings of a ColorRule must agree.
 *
 * MapLibre paints from a style expression; picking and legends evaluate the
 * rule in JS. They previously disagreed about `threshold` in opposite
 * directions, undetected, because no published rule used one yet. This test
 * evaluates both over the same inputs, including the edges where the two
 * implementations differed.
 *
 * Run: npm test
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { colorExpression, paintRank, resolveColor, sortKey } from "./paint.ts";
import type { ColorRule, LayerSpec } from "./types.ts";

/**
 * Minimal MapLibre expression evaluator — only the operators colorExpression
 * emits. Deliberately independent of the builder, so a bug in the builder
 * cannot hide behind a matching bug here.
 */
function evaluate(
  expression: unknown,
  properties: Record<string, unknown>,
): unknown {
  if (!Array.isArray(expression)) return expression;
  const [op, ...args] = expression as [string, ...unknown[]];

  switch (op) {
    case "get":
      return properties[args[0] as string];
    case "has":
      return Object.prototype.hasOwnProperty.call(properties, args[0] as string);
    case "to-string": {
      const value = evaluate(args[0], properties);
      return value === undefined || value === null ? "" : String(value);
    }
    case "to-number": {
      const value = evaluate(args[0], properties);
      if (value === undefined || value === null || value === "") return 0;
      const n = Number(value);
      if (Number.isNaN(n)) throw new Error("to-number: not a number");
      return n;
    }
    case "case": {
      for (let i = 0; i + 1 < args.length; i += 2) {
        if (evaluate(args[i], properties)) return evaluate(args[i + 1], properties);
      }
      return evaluate(args[args.length - 1], properties);
    }
    case "match": {
      const input = evaluate(args[0], properties);
      for (let i = 1; i + 1 < args.length; i += 2) {
        if (args[i] === input) return evaluate(args[i + 1], properties);
      }
      return evaluate(args[args.length - 1], properties);
    }
    case "step": {
      const input = evaluate(args[0], properties) as number;
      let output = evaluate(args[1], properties);
      for (let i = 2; i + 1 < args.length; i += 2) {
        if (input >= (args[i] as number)) output = evaluate(args[i + 1], properties);
        else break;
      }
      return output;
    }
    default:
      throw new Error(`evaluator does not implement "${op}"`);
  }
}

const CATEGORICAL: ColorRule = {
  kind: "categorical",
  field: "st",
  palette: { below: "#c83a3a", meets: "#0c2340", unknown: "#e4dfd6" },
  fallback: "#e4dfd6",
  drawOrder: ["unknown", "meets", "below"],
};

const THRESHOLD: ColorRule = {
  kind: "threshold",
  field: "vpa",
  belowFirst: "#eeeeee",
  bins: [
    { from: 100_000, color: "#aaccee" },
    { from: 500_000, color: "#5588cc" },
    { from: 1_000_000, color: "#c8102e" },
  ],
  fallback: "#999999",
};

function agree(rule: ColorRule, properties: Record<string, unknown>) {
  const painted = evaluate(colorExpression(rule), properties);
  const resolved = resolveColor(rule, properties);
  assert.equal(
    painted,
    resolved,
    `disagreement for ${JSON.stringify(properties)}: painted ${painted}, resolved ${resolved}`,
  );
  return painted;
}

test("constant rule agrees", () => {
  assert.equal(agree({ kind: "constant", color: "#0c2340" }, {}), "#0c2340");
});

test("categorical agrees, including unlisted and missing values", () => {
  assert.equal(agree(CATEGORICAL, { st: "below" }), "#c83a3a");
  assert.equal(agree(CATEGORICAL, { st: "meets" }), "#0c2340");
  assert.equal(agree(CATEGORICAL, { st: "outside" }), "#e4dfd6");
  assert.equal(agree(CATEGORICAL, {}), "#e4dfd6");
});

test("threshold agrees across every bin and both edges", () => {
  // Below the first edge is the case the two implementations got backwards.
  assert.equal(agree(THRESHOLD, { vpa: 0 }), "#eeeeee");
  assert.equal(agree(THRESHOLD, { vpa: 99_999 }), "#eeeeee");
  // `from` is inclusive.
  assert.equal(agree(THRESHOLD, { vpa: 100_000 }), "#aaccee");
  assert.equal(agree(THRESHOLD, { vpa: 499_999 }), "#aaccee");
  assert.equal(agree(THRESHOLD, { vpa: 500_000 }), "#5588cc");
  assert.equal(agree(THRESHOLD, { vpa: 1_000_000 }), "#c8102e");
  assert.equal(agree(THRESHOLD, { vpa: 9_999_999 }), "#c8102e");
});

test("threshold does not colour a missing measurement as the lowest bin", () => {
  // The whole point of the four-state language boundary: absent evidence is
  // not a low value.
  assert.equal(agree(THRESHOLD, {}), "#999999");
});

test("sortKey ranks the consequential state last", () => {
  const layer = { fill: CATEGORICAL } as LayerSpec;
  const key = sortKey(layer);
  assert.equal(evaluate(key, { st: "unknown" }), 0);
  assert.equal(evaluate(key, { st: "meets" }), 1);
  assert.equal(evaluate(key, { st: "below" }), 2);
  assert.equal(evaluate(key, { st: "outside" }), -1);
});

test("paintRank matches sortKey, so picking agrees with painting", () => {
  const layer = { fill: CATEGORICAL } as LayerSpec;
  const key = sortKey(layer);
  for (const st of ["unknown", "meets", "below", "outside"]) {
    assert.equal(
      paintRank(layer, { st }),
      evaluate(key, { st }),
      `paintRank and fill-sort-key disagree for ${st}`,
    );
  }
});
