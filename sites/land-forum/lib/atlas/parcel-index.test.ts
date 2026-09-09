import test from "node:test";
import assert from "node:assert/strict";
import { ParcelIndex } from "./parcel-index.ts";

test("lookup preserves leading zeroes and downloads only the requested shard", async () => {
  const calls: string[] = [];
  const index = new ParcelIndex(async (url) => {
    calls.push(url);
    return url.endsWith("parcel-index.json")
      ? { version: 1, shards: { "00000": "/data/zoning/parcel-index/303030.json", "999": "/data/zoning/parcel-index/393939.json" } }
      : { "000001": [-83.1, 42.36], "000002": [-83.2, 42.37] };
  });
  assert.deepEqual(await index.find("000001"), [-83.1, 42.36]);
  assert.deepEqual(await index.find("000002"), [-83.2, 42.37]);
  assert.deepEqual(calls, ["/data/zoning/parcel-index.json", "/data/zoning/parcel-index/303030.json"]);
  await assert.rejects(index.find("absent"), /not found/);
});

test("invalid lookup data is reported, and failed requests can be retried", async () => {
  let fail = true;
  const index = new ParcelIndex(async () => {
    if (fail) throw new Error("network failed");
    return { version: 0 };
  });
  await assert.rejects(index.find("000001"), /network failed/);
  fail = false;
  await assert.rejects(index.find("000001"), /unexpected format/);
});
