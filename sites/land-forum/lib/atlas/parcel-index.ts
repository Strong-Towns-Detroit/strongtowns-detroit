import { fetchJson } from "./data.ts";
type Point = [number, number];
type Directory = { version: 1; shards: Record<string, string> };

/** Fetch only the ID-prefix shard needed for one lookup. */
export class ParcelIndex {
  private directory?: Directory;
  private shard?: { url: string; rows: Record<string, Point> };
  private readonly fetchData: (url: string) => Promise<unknown>;
  constructor(fetchData: (url: string) => Promise<unknown> = fetchJson) { this.fetchData = fetchData; }

  async find(id: string): Promise<Point> {
    if (!this.directory) {
      const value = await this.fetchData("/data/zoning/parcel-index.json") as Directory;
      if (value?.version !== 1 || !value.shards || typeof value.shards !== "object") {
        throw new Error("Parcel lookup data has an unexpected format.");
      }
      this.directory = value;
    }
    const url = this.directory.shards[id.slice(0, 5)];
    if (typeof url !== "string") throw new Error("Parcel ID not found in this publication.");
    if (!url.startsWith("/data/zoning/parcel-index/")) throw new Error("Invalid parcel lookup location.");
    if (this.shard?.url !== url) {
      const rows = await this.fetchData(url);
      if (!rows || typeof rows !== "object" || Array.isArray(rows)) throw new Error("Invalid parcel lookup records.");
      this.shard = { url, rows: rows as Record<string, Point> };
    }
    const point = this.shard.rows[id];
    if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite)) {
      throw new Error("Parcel ID not found in this publication.");
    }
    return point;
  }
}
