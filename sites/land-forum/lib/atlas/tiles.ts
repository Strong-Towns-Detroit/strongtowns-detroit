/**
 * Reading one tile out of a PMTiles archive, for inspection.
 *
 * MapLibre paints from the archive itself through the `pmtiles://` protocol and
 * never comes through here. This path exists for picking: a click is converted
 * to a tile coordinate, that single tile is decoded, and point-in-polygon finds
 * the parcel. Decoding one tile on demand is far cheaper than keeping hundreds
 * of thousands of GeoJSON features on the main thread so they can be hit-tested.
 */

import { PMTiles } from "pmtiles";
import { load } from "@loaders.gl/core";
import { MVTLoader } from "@loaders.gl/mvt";

const archives = new Map<string, PMTiles>();

/** One archive instance per URL — it caches the header and directory. */
export function archive(url: string): PMTiles {
  let existing = archives.get(url);
  if (!existing) {
    existing = new PMTiles(url);
    archives.set(url, existing);
  }
  return existing;
}

export type TileIndex = { x: number; y: number; z: number };

export type TileFeature = {
  geometry: { type: string; coordinates: unknown };
  properties: Record<string, unknown>;
};

/**
 * Fetch and decode one vector tile.
 *
 * Returns [] rather than throwing when a tile is absent: PMTiles legitimately
 * omits empty tiles, and a missing tile must not tear down the layer.
 */
export async function loadTile(
  url: string,
  sourceLayer: string,
  index: TileIndex,
  signal?: AbortSignal,
): Promise<TileFeature[]> {
  const { z, x, y } = index;

  let response;
  try {
    response = await archive(url).getZxy(z, x, y);
  } catch (error) {
    // A pick can be superseded before its tile arrives. That cancellation is
    // expected; anything else must propagate so a genuinely failed fetch is not
    // mistaken for a tile containing no parcels.
    if (signal?.aborted || isAbort(error)) return [];
    throw error;
  }

  if (!response?.data || signal?.aborted) return [];

  const features = (await load(response.data, MVTLoader, {
    worker: false,
    mvt: {
      // Reproject tile-local coordinates back to lon/lat so picking and the
      // frozen export agree with the rest of the map.
      coordinates: "wgs84",
      tileIndex: { x, y, z },
      layers: [sourceLayer],
    },
  })) as TileFeature[];

  return features ?? [];
}

/**
 * Only a genuine cancellation counts.
 *
 * This used to also match `message === "Failed to fetch"`, which is what a real
 * network failure says too. The effect was that a tile which failed to load
 * resolved to an empty array and was treated as a tile containing no parcels —
 * silently under-reporting the very thing the map exists to count. It showed up
 * as the first render against a cold dev server disagreeing with every render
 * after it.
 *
 * `signal.aborted` is the only trustworthy discriminator; anything else has to
 * propagate so a failed lookup surfaces instead of reading as "no parcel here".
 */
function isAbort(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  return (error as { name?: string }).name === "AbortError";
}

/** Read the archive's own metadata, for zoom bounds and attribution. */
export async function archiveInfo(url: string) {
  const pm = archive(url);
  const header = await pm.getHeader();
  return {
    minZoom: header.minZoom,
    maxZoom: header.maxZoom,
    bounds: [
      header.minLon,
      header.minLat,
      header.maxLon,
      header.maxLat,
    ] as [number, number, number, number],
  };
}
