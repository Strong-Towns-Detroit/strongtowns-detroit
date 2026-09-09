import test from "node:test";
import assert from "node:assert/strict";
import { formatMeasure } from "./format-measure.ts";

test("text evidence and parcel identifiers remain verbatim", () => {
  assert.equal(formatMeasure("R1", "text"), "R1");
  assert.equal(formatMeasure("0001", "text"), "0001");
});

test("recorded zero differs from missing or invalid measurements", () => {
  assert.equal(formatMeasure(0, "currency"), "$0");
  assert.equal(formatMeasure(null, "currency"), "Not recorded");
  assert.equal(formatMeasure(0, "sqft"), "Not recorded");
  assert.equal(formatMeasure(0, "sqft", true), "0 sq. ft.");
  assert.equal(formatMeasure(-1, "sqft", true), "Not recorded");
  assert.equal(formatMeasure("invalid", "feet"), "Not recorded");
});
