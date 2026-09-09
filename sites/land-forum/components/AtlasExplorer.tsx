"use client";

import DataSources from "./DataSources";
import { matchesBzaCase } from "../lib/graphics/bza";

import { useEffect, useMemo, useRef, useState } from "react";
import { fetchJson, records, safeSourceUrl, readAtlasState, writeAtlasState, type AtlasState } from "../lib/atlas/data";
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  MapGeoJSONFeature,
  Popup,
} from "maplibre-gl";

type CaseRecord = {
  id: string;
  caseNumber: string;
  address: string;
  location: string;
  petitioner: string;
  proposal: string;
  category: string;
  categoryLabel: string;
  outcome: string;
  outcomeLabel: string;
  firstDate: string;
  lastDate: string;
  appearances: number;
  hearings: {
    date: string;
    status: string;
    decision: string;
    file: string;
    sourceUrl?: string | null;
  }[];
  lat: number;
  lon: number;
};

type MapSite = {
  id: string;
  category: string;
  categoryLabel: string;
  appearances: number;
  caseIds: string[];
  lat: number;
  lon: number;
};

const CATEGORY_COLORS: Record<string, string> = {
  "Administrative/community appeal": "#0c2340",
  "Parking supply": "#c83a3a",
  Parking: "#c83a3a",
  "Density/unit count": "#006d77",
  "Building design standards": "#9b5de5",
  Hardship: "#bc6c25",
  "Use spacing/separation": "#0072ce",
  "Setbacks/yards": "#e57f00",
  "Nonconforming use/structure": "#43617f",
  "Lot coverage": "#d85b68",
  "Lot dimensions": "#75a7db",
  Height: "#b96f00",
  "Parking layout": "#173e67",
  "Screening/landscaping": "#a92f43",
  "Signs/billboards": "#5f8fbe",
  "Floor area/bulk": "#d2a944",
  "Multiple buildings": "#647184",
  "Open/recreation space": "#8f5261",
  "Fences/walls": "#90b8e8",
  Loading: "#927035",
  "Request not specified": "#73777d",
};

function FilterChecklist({
  label,
  values,
  selected,
  onChange,
  colors,
}: {
  label: string;
  values: string[];
  selected: string[];
  onChange: (values: string[]) => void;
  colors?: Record<string, string>;
}) {
  function toggle(value: string) {
    onChange(
      selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value],
    );
  }

  return (
    <details className="filter-menu">
      <summary>
        <span>{label}</span>
        <b>{selected.length ? selected.length : "All"}</b>
      </summary>
      <div className="filter-options">
        <div className="filter-menu-heading">
          <strong>{label}</strong>
          {selected.length > 0 && (
            <button type="button" onClick={() => onChange([])}>Clear</button>
          )}
        </div>
        {[...new Set([...values, ...selected])].map((value) => (
          <label key={value}>
            <input
              type="checkbox"
              checked={selected.includes(value)}
              onChange={() => toggle(value)}
            />
            <span className="custom-check" aria-hidden="true" />
            {colors?.[value] && (
              <span
                className="filter-swatch"
                style={{ background: colors[value] }}
                aria-hidden="true"
              />
            )}
            <span>{value}</span>
          </label>
        ))}
      </div>
    </details>
  );
}

type PieSegment = { color: string; count: number };

function markerImageId(segments: PieSegment[]) {
  const signature = segments
    .map((segment) => `${segment.color}:${segment.count}`)
    .join("|");
  let hash = 5381;
  for (let index = 0; index < signature.length; index += 1) {
    hash = ((hash << 5) + hash) ^ signature.charCodeAt(index);
  }
  return `site-pie-${(hash >>> 0).toString(36)}`;
}

function addPieMarker(map: MapLibreMap, segments: PieSegment[]) {
  const id = markerImageId(segments);
  if (map.hasImage(id)) return id;

  const size = 24;
  const pixelRatio = 2;
  const canvas = document.createElement("canvas");
  canvas.width = size * pixelRatio;
  canvas.height = size * pixelRatio;
  const context = canvas.getContext("2d");
  if (!context) return id;
  context.scale(pixelRatio, pixelRatio);

  const center = size / 2;
  const radius = 9;
  const total = segments.reduce((sum, segment) => sum + segment.count, 0);
  let cursor = -Math.PI / 2;
  segments.forEach((segment) => {
    const end = cursor + (segment.count / total) * Math.PI * 2;
    context.beginPath();
    context.moveTo(center, center);
    context.arc(center, center, radius, cursor, end);
    context.closePath();
    context.fillStyle = segment.color;
    context.fill();
    if (segments.length > 1) {
      context.strokeStyle = "#fffaf0";
      context.lineWidth = 0.8;
      context.stroke();
    }
    cursor = end;
  });
  context.beginPath();
  context.arc(center, center, radius, 0, Math.PI * 2);
  context.strokeStyle = "#fffaf0";
  context.lineWidth = 1.4;
  context.stroke();

  map.addImage(id, context.getImageData(0, 0, canvas.width, canvas.height), {
    pixelRatio,
  });
  return id;
}

export default function AtlasExplorer() {
  const mapNode = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const popupRef = useRef<Popup | null>(null);
  const casesRef = useRef<CaseRecord[]>([]);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [mapSites, setMapSites] = useState<MapSite[]>([]);
  const [mapContext, setMapContext] = useState<GeoJSON.FeatureCollection | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [urlState, setUrlState] = useState<AtlasState>(readAtlasState(""));
  const query = urlState.q;
  const selectedCategories = urlState.category;
  const selectedOutcomes = urlState.outcome;
  const selectedYears = urlState.year;
  const selected = cases.find((item) => item.id === urlState.case) ?? null;
  const updateUrl = (patch: Partial<AtlasState>, mode: "pushState" | "replaceState" = "pushState") => {
    const next = { ...readAtlasState(window.location.search), ...patch };
    const search = writeAtlasState(next, window.location.search);
    window.history[mode](null, "", `${window.location.pathname}${search ? `?${search}` : ""}${window.location.hash}`);
    setUrlState(next);
  };
  const setQuery = (q: string) => updateUrl({ q }, "replaceState");
  const setSelectedCategories = (category: string[]) => updateUrl({ category });
  const setSelectedOutcomes = (outcome: string[]) => updateUrl({ outcome });
  const setSelectedYears = (year: string[]) => updateUrl({ year });
  const setSelected = (item: CaseRecord | null) => updateUrl({ case: item?.id ?? "" });
  const [dataError, setDataError] = useState("");
  const [mapError, setMapError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const detailRef = useRef<HTMLElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const restore = () => setUrlState(readAtlasState(window.location.search));
    restore();
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, []);
  useEffect(() => {
    if (selected) {
      previousFocus.current = document.activeElement as HTMLElement;
      detailRef.current?.focus();
    } else previousFocus.current?.focus();
  }, [selected?.id]);
  useEffect(() => {
    if (selected && mapReady) mapRef.current?.flyTo({ center: [selected.lon, selected.lat], zoom: 15, duration: 0 });
  }, [selected?.id, mapReady]);
  const [selectedSite, setSelectedSite] = useState<CaseRecord[]>([]);

  useEffect(() => {
    casesRef.current = cases;
  }, [cases]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setDataError("");
    setMapError("");
    fetchJson("/data/bza-cases.json", controller.signal).then((value) => {
      const rows = records(value, ["id", "caseNumber", "address", "location", "petitioner", "proposal", "category", "categoryLabel", "outcome", "outcomeLabel", "firstDate", "lastDate"], ["appearances", "lat", "lon"]);
      for (const row of rows) records(row.hearings, ["date", "status", "decision", "file"], []);
      if (!controller.signal.aborted) setCases(rows as unknown as CaseRecord[]);
    }).catch((error) => {
      if (!controller.signal.aborted) setDataError(String(error.message));
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    Promise.all([
      fetchJson("/data/bza-map.json", controller.signal),
      fetchJson("/data/detroit-context.geojson", controller.signal),
    ]).then(([sites, context]) => {
      const rows = records(sites, ["id", "category", "categoryLabel"], ["appearances", "lat", "lon"]);
      if (!rows.every((row) => Array.isArray(row.caseIds) && row.caseIds.every((id) => typeof id === "string"))) throw new Error("Invalid map case identifiers.");
      const geo = context as GeoJSON.FeatureCollection;
      if (geo?.type !== "FeatureCollection" || !Array.isArray(geo.features)) throw new Error("Invalid map context.");
      if (!controller.signal.aborted) {
        setMapSites(rows as unknown as MapSite[]);
        setMapContext(geo);
      }
    }).catch((error) => { if (!controller.signal.aborted) setMapError(String(error.message)); });
    return () => controller.abort();
  }, [attempt]);

  const filtered = useMemo(() => {
    return cases.filter((item) => matchesBzaCase(item, {
      q: query, categories: selectedCategories, outcomes: selectedOutcomes, years: selectedYears,
    }));
  }, [cases, query, selectedCategories, selectedOutcomes, selectedYears]);

  const categories = useMemo(
    () => [...new Set(cases.map((item) => item.categoryLabel))].sort(),
    [cases],
  );
  const outcomes = useMemo(
    () => [...new Set(cases.map((item) => item.outcomeLabel))].sort(),
    [cases],
  );
  const years = useMemo(
    () => [...new Set(cases.map((item) => item.firstDate.slice(0, 4)))].sort(),
    [cases],
  );

  useEffect(() => {
    if (!mapNode.current || mapRef.current) return;
    let cancelled = false;
    import("maplibre-gl").then((maplibregl) => {
      if (cancelled || !mapNode.current) return;
      maplibregl.setWorkerUrl(
        "/vendor/maplibre-gl/maplibre-gl-worker.mjs",
      );
      const map = new maplibregl.Map({
        container: mapNode.current,
        style: {
          version: 8,
          sources: {},
          layers: [{
            id: "background",
            type: "background",
            paint: { "background-color": "#fffaf0" },
          }],
        },
        center: [-83.1, 42.36],
        zoom: 10,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
      });
      map.addControl(
        new maplibregl.NavigationControl({
          showCompass: false,
          visualizePitch: false,
        }),
        "top-left",
      );
      mapRef.current = map;
      map.on("error", () => { if (!cancelled) setMapError("The map could not load. Case records remain available."); });
      map.once("load", () => {
        if (!cancelled) setMapReady(true);
      });
    }).catch(() => { if (!cancelled) setMapError("The map could not start. Case records remain available."); });
    return () => {
      cancelled = true;
      popupRef.current?.remove();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !mapReady || !mapContext) return;
    const map = mapRef.current;
    if (!map.getSource("detroit-context")) {
      map.addSource("detroit-context", {
        type: "geojson",
        data: mapContext,
      });
      map.addLayer({
        id: "detroit-city",
        type: "fill",
        source: "detroit-context",
        filter: ["==", ["get", "kind"], "city"],
        paint: {
          "fill-color": "#ebe5da",
          "fill-opacity": 1,
          "fill-outline-color": "#d8d0c3",
        },
      });
      map.addLayer({
        id: "detroit-roads",
        type: "line",
        source: "detroit-context",
        filter: ["!=", ["get", "kind"], "city"],
        layout: {
          "line-cap": "round",
          "line-join": "round",
        },
        paint: {
          // Use pre-blended opaque colors rather than translucent navy.
          // Coincident segment caps otherwise darken at every OSM graph node.
          "line-color": [
            "interpolate", ["linear"], ["zoom"],
            10, "#adafaf",
            12, "#8f9399",
            16, "#6a747b",
          ],
          "line-width": [
            "interpolate", ["exponential", 1.35], ["zoom"],
            10, ["*", ["get", "roadWidthM"], 0.055],
            12, ["*", ["get", "roadWidthM"], 0.12],
            14, ["*", ["get", "roadWidthM"], 0.28],
            16, ["*", ["get", "roadWidthM"], 0.70],
            18, ["*", ["get", "roadWidthM"], 1.40],
          ],
          "line-opacity": 1,
        },
      });
      map.addSource("bza-sites", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "bza-sites",
        type: "symbol",
        source: "bza-sites",
        layout: {
          "icon-image": ["get", "iconId"],
          "icon-size": 1,
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
      });
      map.fitBounds(
        [[-83.305, 42.245], [-82.91, 42.46]],
        { padding: 20, duration: 0 },
      );
    } else {
      (map.getSource("detroit-context") as GeoJSONSource).setData(mapContext);
    }
  }, [mapReady, mapContext]);

  useEffect(() => {
    if (!mapRef.current || !mapReady || !mapRef.current.getSource("bza-sites")) return;
    const visibleIds = new Set(filtered.map((item) => item.id));
    const caseById = new Map(cases.map((item) => [item.id, item]));
    const groupedSites = new Map<string, {
      lat: number;
      lon: number;
      caseIds: Set<string>;
    }>();
    mapSites.forEach((site) => {
      const key = `${site.lat.toFixed(6)}:${site.lon.toFixed(6)}`;
      const group = groupedSites.get(key) || {
        lat: site.lat,
        lon: site.lon,
        caseIds: new Set<string>(),
      };
      site.caseIds.forEach((caseId) => group.caseIds.add(caseId));
      groupedSites.set(key, group);
    });
    const features: GeoJSON.Feature<GeoJSON.Point>[] = [...groupedSites.values()]
      .flatMap((site): GeoJSON.Feature<GeoJSON.Point>[] => {
        const activeCases = [...site.caseIds]
          .filter((caseId) => visibleIds.has(caseId))
          .map((caseId) => caseById.get(caseId))
          .filter((item): item is CaseRecord => Boolean(item))
          .sort((left, right) => left.firstDate.localeCompare(right.firstDate));
        if (!activeCases.length) return [];
        const lead = activeCases[0];
        const years = new Set(activeCases.map(
          (item) => item.firstDate.slice(0, 4),
        ));
        const categoryCounts = new Map<string, number>();
        activeCases.forEach((item) => {
          categoryCounts.set(
            item.categoryLabel,
            (categoryCounts.get(item.categoryLabel) || 0) + 1,
          );
        });
        const segments = [...categoryCounts.entries()]
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([label, count]) => ({
            color: CATEGORY_COLORS[label] || "#73777d",
            count,
          }));
        const iconId = addPieMarker(mapRef.current!, segments);
        return [{
          type: "Feature",
          geometry: { type: "Point", coordinates: [site.lon, site.lat] },
          properties: {
            leadId: lead?.id || "",
            caseIds: JSON.stringify(activeCases.map((item) => item.id)),
            caseCount: activeCases.length,
            yearCount: years.size,
            iconId,
            label: activeCases.length > 1
              ? `${activeCases.length} cases · ${years.size} ${
                years.size === 1 ? "year" : "years"
              } · ${lead.address}`
              : `${lead?.caseNumber || "BZA case"} · ${lead?.address || ""}`,
          },
        }];
      });
    (mapRef.current.getSource("bza-sites") as GeoJSONSource).setData({
      type: "FeatureCollection",
      features,
    });
  }, [filtered, cases, mapSites, mapReady]);

  useEffect(() => {
    if (!mapRef.current || !mapReady || !mapRef.current.getLayer("bza-sites")) return;
    const map = mapRef.current;
    let popup: Popup | null = null;
    const siteCases = (features?: MapGeoJSONFeature[]) => {
      const serialized = features?.[0]?.properties?.caseIds;
      if (!serialized) return [];
      const ids = JSON.parse(serialized) as string[];
      return ids
        .map((id) => casesRef.current.find((item) => item.id === id))
        .filter((item): item is CaseRecord => Boolean(item));
    };
    const onClick = (event: { features?: MapGeoJSONFeature[] }) => {
      const items = siteCases(event.features);
      setSelectedSite(items);
      setSelected(items.length === 1 ? items[0] : null);
    };
    const onEnter = (
      event: { features?: MapGeoJSONFeature[]; lngLat: { lng: number; lat: number } },
    ) => {
      map.getCanvas().style.cursor = "pointer";
      const feature = event.features?.[0];
      const label = feature?.properties?.label;
      if (!label) return;
      const anchor = feature.geometry.type === "Point"
        ? feature.geometry.coordinates as [number, number]
        : [event.lngLat.lng, event.lngLat.lat] as [number, number];
      import("maplibre-gl").then((maplibregl) => {
        popup?.remove();
        popup = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          offset: 12,
          className: "atlas-tooltip",
        })
          .setLngLat(anchor)
          .setText(label)
          .addTo(map);
        popupRef.current = popup;
      });
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = "";
      popup?.remove();
      popup = null;
      popupRef.current = null;
    };
    map.on("click", "bza-sites", onClick);
    map.on("mouseenter", "bza-sites", onEnter);
    map.on("mouseleave", "bza-sites", onLeave);
    return () => {
      map.off("click", "bza-sites", onClick);
      map.off("mouseenter", "bza-sites", onEnter);
      map.off("mouseleave", "bza-sites", onLeave);
      popup?.remove();
    };
  }, [mapReady, mapContext]);

  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;
    const resize = new ResizeObserver(() => map.resize());
    if (mapNode.current) resize.observe(mapNode.current);
    return () => resize.disconnect();
  }, [mapReady]);

  function chooseCase(item: CaseRecord) {
    setSelected(item);
    const matchingSite = mapSites.find((site) => site.caseIds.includes(item.id));
    const relatedIds = matchingSite
      ? mapSites
        .filter((site) =>
          Math.abs(site.lat - matchingSite.lat) < 0.000001
          && Math.abs(site.lon - matchingSite.lon) < 0.000001
        )
        .flatMap((site) => site.caseIds)
      : [item.id];
    setSelectedSite(
      [...new Set(relatedIds)]
        .map((id) => cases.find((record) => record.id === id))
        .filter((record): record is CaseRecord => Boolean(record)),
    );
    mapRef.current?.flyTo({
      center: [item.lon, item.lat],
      zoom: 15,
      duration: 600,
    });
  }

  return (
    <section className="explorer">
      <aside className="filter-panel">
        <a className="project-link" href={`/graphics/bza/?from=atlas&${writeAtlasState({ ...urlState, case: '' })}`}>Create a graphic from these cases</a>
        <label className="search-label">
          <span>Search cases</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Address, petitioner, or case no."
          />
        </label>
        <div className="filter-grid">
          <FilterChecklist
            label="Request"
            values={categories}
            selected={selectedCategories}
            onChange={setSelectedCategories}
            colors={CATEGORY_COLORS}
          />
          <FilterChecklist
            label="Outcome"
            values={outcomes}
            selected={selectedOutcomes}
            onChange={setSelectedOutcomes}
          />
          <FilterChecklist
            label="First heard"
            values={years}
            selected={selectedYears}
            onChange={setSelectedYears}
          />
        </div>
        {loading && <p role="status">Loading case records…</p>}
        {dataError && <p role="alert">{dataError} <button onClick={() => setAttempt(attempt + 1)}>Retry data</button></p>}
        {!loading && !dataError && filtered.length === 0 && <p role="status">No cases match these filters.</p>}
        <div className="results-heading" aria-live="polite">
          <strong>{filtered.length}</strong>
          <span>{filtered.length === 1 ? "case" : "cases"}</span>
        </div>
        <ul className="case-list" style={{ listStyle: "none", padding: 0 }}>
          {filtered.map((item) => (
            <li key={item.id}><button
              className={selected?.id === item.id ? "case-card selected" : "case-card"}
              key={item.id}
              onClick={() => chooseCase(item)}
              type="button"
            >
              <span
                className="case-swatch"
                style={{ background: CATEGORY_COLORS[item.categoryLabel] }}
              />
              <span>
                <b>{item.address}</b>
                <small>{item.caseNumber} · {item.firstDate.slice(0, 4)}</small>
                <small>{item.categoryLabel}</small>
              </span>
            </button></li>
          ))}
        </ul>
        <DataSources kind="bza" />
      </aside>
      <div className="map-region">
        {mapError && <p role="alert">{mapError} <button onClick={() => window.location.reload()}>Reload map</button></p>}
        <div ref={mapNode} className="map" aria-label="Map of Detroit BZA cases" />
        <div className="map-note">
          Pie area shows the mix of request types at a site. Like requests are
          combined; select a marker to see cases grouped by year.
        </div>
        {selectedSite.length > 1 && !selected && (
          <article className="case-detail site-detail">
            <button
              className="detail-close"
              onClick={() => setSelectedSite([])}
              aria-label="Close site details"
            >×</button>
            <p className="kicker">Multiple cases at one site</p>
            <h2>{selectedSite[0].address}</h2>
            <p className="detail-meta">
              {selectedSite.length} cases across {
                new Set(selectedSite.map((item) => item.firstDate.slice(0, 4))).size
              } years
            </p>
            <div className="site-year-groups">
              {[...new Set(selectedSite.map(
                (item) => item.firstDate.slice(0, 4),
              ))].sort().reverse().map((siteYear) => (
                <section key={siteYear}>
                  <h3>{siteYear}</h3>
                  <div className="site-year-cases">
                    {selectedSite
                      .filter((item) => item.firstDate.startsWith(siteYear))
                      .map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => setSelected(item)}
                        >
                          <span
                            className="case-swatch"
                            style={{ background: CATEGORY_COLORS[item.categoryLabel] }}
                          />
                          <span>
                            <b>{item.caseNumber}</b>
                            <small>{item.categoryLabel}</small>
                            <small>{item.outcomeLabel}</small>
                          </span>
                        </button>
                      ))}
                  </div>
                </section>
              ))}
            </div>
          </article>
        )}
        {selected && (
          <article className="case-detail" ref={detailRef} tabIndex={-1} aria-label="Selected case">
            <button
              className="detail-close"
              onClick={() => {
                setSelected(null);
                setSelectedSite([]);
              }}
              aria-label="Close case details"
            >×</button>
            {selectedSite.length > 1 && (
              <button
                className="detail-back"
                type="button"
                onClick={() => setSelected(null)}
              >← All cases at this site</button>
            )}
            <p className="kicker">{selected.caseNumber} · {selected.outcomeLabel}</p>
            <h2>{selected.address}</h2>
            <p className="detail-meta">{selected.petitioner}</p>
            <dl>
              <div><dt>Request</dt><dd>{selected.categoryLabel}</dd></div>
              <div><dt>First heard</dt><dd>{selected.firstDate}</dd></div>
              <div><dt>Last heard</dt><dd>{selected.lastDate}</dd></div>
              <div><dt>Appearances</dt><dd>{selected.appearances}</dd></div>
            </dl>
            <p className="proposal">{selected.proposal}</p>
            {selected.hearings.length > 0 && (
              <section className="hearing-files">
                <h3>Meeting records</h3>
                {selected.hearings.map((hearing) => (
                  <div
                    key={`${hearing.date}:${hearing.file}`}
                  >
                    <span>
                      <b>{hearing.date}</b>
                      <small>{hearing.decision || hearing.status}</small>
                    </span>
                    {safeSourceUrl(hearing.sourceUrl)
                      ? <a href={safeSourceUrl(hearing.sourceUrl)!}>{hearing.file || "View meeting record"}</a>
                      : <span>{hearing.file}<small>Source link unavailable</small></span>}
                  </div>
                ))}
              </section>
            )}
          </article>
        )}
      </div>
    </section>
  );
}
