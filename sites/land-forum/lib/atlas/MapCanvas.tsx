"use client";

/**
 * The shared map renderer.
 *
 * MapLibre reads MVT tiles directly from PMTiles.  This is intentionally a
 * native vector-tile path: MapLibre parses tiles in its worker pool and builds
 * GPU buckets without first materialising hundreds of thousands of GeoJSON
 * objects on the main thread.  All parcel features remain present at every
 * authored zoom level.
 *
 * Inspection is separate from painting.  A click is converted to a z15 tile
 * coordinate, that one tile is decoded, and point-in-polygon identifies the
 * parcel.  The visible layer therefore does not need picking attributes.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";
import { Protocol } from "pmtiles";
import { loadTile } from "./tiles";
import { colorExpression, paintRank, sortKey } from "./paint";
import type { MapSpec, ViewState } from "./types";

export type PickedFeature = {
  layerId: string;
  properties: Record<string, unknown>;
};

type Props = {
  spec: MapSpec;
  width?: number;
  height?: number;
  frozen?: boolean;
  onPick?: (feature: PickedFeature | null) => void;
  onViewStateChange?: (view: ViewState) => void;
  selectedId?: string | null;
  className?: string;
};

let protocolInstalled = false;

function tileAt(lon: number, lat: number, z: number) {
  const n = 2 ** z;
  const x = Math.floor(((lon + 180) / 360) * n);
  const radians = (lat * Math.PI) / 180;
  const y = Math.floor(
    ((1 - Math.asinh(Math.tan(radians)) / Math.PI) / 2) * n,
  );
  return { x, y, z };
}

type Position = [number, number];

function pointInRing(point: Position, ring: Position[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    const crosses =
      yi > point[1] !== yj > point[1]
      && point[0] < ((xj - xi) * (point[1] - yi)) / (yj - yi) + xi;
    if (crosses) inside = !inside;
  }
  return inside;
}

function pointInPolygon(point: Position, rings: Position[][]): boolean {
  if (!rings.length || !pointInRing(point, rings[0])) return false;
  return !rings.slice(1).some((hole) => pointInRing(point, hole));
}

function containsPoint(geometry: { type: string; coordinates: unknown }, point: Position) {
  if (geometry.type === "Polygon") {
    return pointInPolygon(point, geometry.coordinates as Position[][]);
  }
  if (geometry.type === "MultiPolygon") {
    return (geometry.coordinates as Position[][][]).some((polygon) =>
      pointInPolygon(point, polygon),
    );
  }
  return false;
}

export default function MapCanvas({
  spec,
  width,
  height,
  frozen = false,
  onPick,
  onViewStateChange,
  className,
}: Props) {
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const pickRef = useRef(onPick);
  pickRef.current = onPick;
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    let cancelled = false;

    (async () => {
      const maplibregl = await import("maplibre-gl");
      if (cancelled || !container.current) return;

      maplibregl.setWorkerUrl("/vendor/maplibre-gl/maplibre-gl-worker.mjs");
      if (!protocolInstalled) {
        const protocol = new Protocol();
        maplibregl.addProtocol("pmtiles", protocol.tile);
        protocolInstalled = true;
      }

      const map = new maplibregl.Map({
        container: container.current,
        style: {
          version: 8,
          sources: {},
          layers: [{
            id: "ground",
            type: "background",
            paint: { "background-color": "#fffaf0" },
          }],
        },
        center: [spec.view.longitude, spec.view.latitude],
        zoom: spec.view.zoom,
        minZoom: spec.minZoom,
        maxZoom: spec.maxZoom,
        bearing: spec.view.bearing ?? 0,
        pitch: spec.view.pitch ?? 0,
        attributionControl: false,
        interactive: !frozen,
        dragRotate: false,
        pitchWithRotate: false,
        canvasContextAttributes: {
          preserveDrawingBuffer: frozen,
          antialias: frozen,
        },
        fadeDuration: frozen ? 0 : 300,
      });
      mapRef.current = map;

      if (spec.bounds) {
        map.fitBounds(spec.bounds, {
          padding: spec.fitPadding ?? 0,
          animate: false,
        });
      }

      if (!frozen) {
        map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
        map.on("moveend", () => {
          const center = map.getCenter();
          onViewStateChange?.({
            longitude: center.lng,
            latitude: center.lat,
            zoom: map.getZoom(),
          });
        });
      }

      map.once("load", () => {
        const sourceIds = new Map<string, string>();
        for (const layer of spec.layers) {
          let sourceId = sourceIds.get(layer.source.url);
          if (!sourceId) {
            sourceId = `pmtiles-${sourceIds.size}`;
            sourceIds.set(layer.source.url, sourceId);
            const absolute = new URL(layer.source.url, window.location.href).href;
            map.addSource(sourceId, {
              type: "vector",
              url: `pmtiles://${absolute}`,
            });
          }

          if (layer.geometry === "polygon") {
            const key = sortKey(layer);
            map.addLayer({
              id: layer.id,
              type: "fill",
              source: sourceId,
              "source-layer": layer.source.sourceLayer,
              minzoom: layer.minZoom,
              maxzoom: layer.maxZoom,
              layout: key ? { "fill-sort-key": key } : {},
              paint: {
                "fill-color": colorExpression(layer.fill),
                "fill-opacity": layer.opacity ?? 1,
                "fill-antialias": false,
              },
            } as never);
          } else {
            map.addLayer({
              id: layer.id,
              type: "line",
              source: sourceId,
              "source-layer": layer.source.sourceLayer,
              minzoom: layer.minZoom,
              maxzoom: layer.maxZoom,
              layout: { "line-cap": "round", "line-join": "round" },
              paint: {
                "line-color": colorExpression(layer.stroke?.color),
                "line-width": layer.stroke?.widthPx ?? 1,
                "line-opacity": layer.opacity ?? 1,
              },
            } as never);
          }
        }

        map.once("idle", () => setReady(true));
      });

      if (!frozen && spec.inspect) {
        map.on("click", async (event) => {
          const target = spec.layers.find((layer) => layer.id === spec.inspect!.layerId);
          if (!target) return;
          const lookup = spec.inspect!.lookupSource ?? target.source;
          const lookupZoom = spec.inspect!.lookupZoom ?? 15;
          const index = tileAt(event.lngLat.lng, event.lngLat.lat, lookupZoom);
          const features = await loadTile(
            lookup.url,
            lookup.sourceLayer,
            index,
          );
          const point: Position = [event.lngLat.lng, event.lngLat.lat];
          // Assessor parcels overlap, so more than one can contain the click.
          // `fill-sort-key` decides which one the reader can actually see;
          // taking the first tile-order match would let the inspector name a
          // parcel hidden underneath it.
          const hits = features.filter((candidate) =>
            containsPoint(candidate.geometry, point),
          );
          const feature = hits.reduce<(typeof hits)[number] | undefined>(
            (best, candidate) =>
              best === undefined
              || paintRank(target, candidate.properties)
                 >= paintRank(target, best.properties)
                ? candidate
                : best,
            undefined,
          );
          pickRef.current?.(
            feature
              ? { layerId: target.id, properties: feature.properties }
              : null,
          );
        });
      }
    })();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // Map specs are stable configuration objects for the lifetime of a route.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const style = useMemo(
    () => width && height ? { width: `${width}px`, height: `${height}px` } : undefined,
    [width, height],
  );

  return (
    <div
      ref={container}
      className={className}
      style={style}
      data-map-ready={ready ? "true" : "false"}
      role="img"
      aria-label={`${spec.title}. ${spec.subtitle}`}
    >
    </div>
  );
}
