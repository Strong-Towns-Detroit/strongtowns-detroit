import test from "node:test";
import assert from "node:assert/strict";
import { fetchJson, records, safeSourceUrl, readAtlasState, writeAtlasState } from "./data.ts";

test("shared filters and case IDs round trip without losing unrelated parameters", () => {
  const state = { q: "A & B", category: ["Lot dimensions", "Height"], outcome: ["Granted"], year: ["2024"], case: "case/17" };
  const encoded = writeAtlasState(state, "campaign=forum&category=old");
  assert.deepEqual(readAtlasState(encoded), state);
  assert.equal(new URLSearchParams(encoded).get("campaign"), "forum");
  assert.equal(readAtlasState("").case, "");
});

test("empty records are valid but malformed records and coordinates fail", () => {
  assert.deepEqual(records([], ["id"], ["lat"]), []);
  assert.throws(() => records([{ id: "a", lat: null }], ["id"], ["lat"]));
  assert.throws(() => records({}, [], []));
  assert.throws(() => records([{ id: "a", lat: Infinity }], ["id"], ["lat"]));
});

test("only HTTP source links are presented", () => {
  assert.equal(safeSourceUrl("javascript:alert(1)"), null);
  assert.equal(safeSourceUrl("minutes.pdf"), null);
  assert.equal(safeSourceUrl(null), null);
  assert.equal(safeSourceUrl("https://example.org/minutes.pdf"), "https://example.org/minutes.pdf");
});

test("HTTP failure is distinguished from an empty successful response", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response("[]", { status: 503 }));
  await assert.rejects(fetchJson("/cases"), /503/);
  t.mock.restoreAll();
  t.mock.method(globalThis, "fetch", async () => new Response("[]", { status: 200 }));
  assert.deepEqual(await fetchJson("/cases"), []);
});

