"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { CircleMarker, Map as LeafletMap } from "leaflet";

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

export default function AtlasExplorer() {
  const mapNode = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<CircleMarker[]>([]);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [mapSites, setMapSites] = useState<MapSite[]>([]);
  const [mapContext, setMapContext] = useState<GeoJSON.FeatureCollection | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All requests");
  const [outcome, setOutcome] = useState("All outcomes");
  const [year, setYear] = useState("All years");
  const [selected, setSelected] = useState<CaseRecord | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/data/bza-cases.json").then((response) => response.json()),
      fetch("/data/bza-map.json").then((response) => response.json()),
      fetch("/data/detroit-context.geojson").then((response) => response.json()),
    ]).then(([caseData, siteData, contextData]) => {
      setCases(caseData);
      setMapSites(siteData);
      setMapContext(contextData);
    });
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return cases.filter((item) => {
      const searchable = [
        item.caseNumber, item.address, item.location, item.petitioner,
      ].join(" ").toLowerCase();
      return (!needle || searchable.includes(needle))
        && (category === "All requests" || item.categoryLabel === category)
        && (outcome === "All outcomes" || item.outcomeLabel === outcome)
        && (year === "All years" || item.firstDate.startsWith(year));
    });
  }, [cases, query, category, outcome, year]);

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
    import("leaflet").then((L) => {
      if (cancelled || !mapNode.current) return;
      const map = L.map(mapNode.current, {
        zoomControl: true,
        attributionControl: false,
        zoomSnap: 0.25,
      });
      mapRef.current = map;
      setMapReady(true);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !mapReady || !mapContext) return;
    let cancelled = false;
    import("leaflet").then((L) => {
      if (cancelled || !mapRef.current) return;
      const contextLayer = L.geoJSON(mapContext, {
        style: (feature) => {
          if (feature?.properties?.kind === "city") {
            return {
              fillColor: "#ebe5da",
              fillOpacity: 1,
              color: "#d8d0c3",
              weight: 0.7,
            };
          }
          return {
            color: "#0c2340",
            weight: feature?.properties?.roadClass === "major" ? 0.75 : 0.48,
            opacity: feature?.properties?.roadClass === "major" ? 0.34 : 0.24,
          };
        },
      }).addTo(mapRef.current);
      const cityFeature = mapContext.features.find(
        (feature) => feature.properties?.kind === "city",
      );
      if (cityFeature) {
        const cityLayer = L.geoJSON(cityFeature);
        mapRef.current.fitBounds(
          cityLayer.getBounds().pad(0.055),
          { padding: [20, 20] },
        );
      } else {
        mapRef.current.fitBounds(
          [[42.245, -83.305], [42.46, -82.91]],
          { padding: [20, 20] },
        );
      }
      return () => contextLayer.remove();
    });
    return () => { cancelled = true; };
  }, [mapReady, mapContext]);

  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    let cancelled = false;
    import("leaflet").then((L) => {
      if (cancelled || !mapRef.current) return;
      layerRef.current.forEach((layer) => layer.remove());
      const visibleIds = new Set(filtered.map((item) => item.id));
      const caseById = new Map(cases.map((item) => [item.id, item]));
      const visibleSites = mapSites.filter((site) =>
        site.caseIds.some((caseId) => visibleIds.has(caseId)),
      );
      layerRef.current = visibleSites.map((site) => {
        const activeCases = site.caseIds
          .filter((caseId) => visibleIds.has(caseId))
          .map((caseId) => caseById.get(caseId))
          .filter((item): item is CaseRecord => Boolean(item));
        const appearances = activeCases.reduce(
          (total, item) => total + item.appearances, 0,
        );
        const marker = L.circleMarker([site.lat, site.lon], {
          radius: 4.8 + Math.sqrt(Math.max(1, appearances)) * 2.15,
          color: "#fffaf0",
          weight: 1.5,
          fillColor: CATEGORY_COLORS[site.categoryLabel] || "#73777d",
          fillOpacity: 0.84,
        });
        const lead = activeCases[0];
        const label = activeCases.length > 1
          ? `${activeCases.length} related cases at this site`
          : `${lead?.caseNumber || "BZA case"} · ${lead?.address || ""}`;
        marker
          .bindTooltip(label, { direction: "top" })
          .on("click", () => lead && setSelected(lead))
          .addTo(mapRef.current!);
        return marker;
      });
    });
    return () => { cancelled = true; };
  }, [filtered, cases, mapSites, mapReady]);

  function chooseCase(item: CaseRecord) {
    setSelected(item);
    mapRef.current?.flyTo([item.lat, item.lon], 15, { duration: 0.6 });
  }

  return (
    <section className="explorer">
      <aside className="filter-panel">
        <label className="search-label">
          <span>Search cases</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Address, petitioner, or case no."
          />
        </label>
        <div className="select-grid">
          <label>Request
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option>All requests</option>
              {categories.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label>Outcome
            <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              <option>All outcomes</option>
              {outcomes.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label>First heard
            <select value={year} onChange={(e) => setYear(e.target.value)}>
              <option>All years</option>
              {years.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
        </div>
        <div className="results-heading">
          <strong>{filtered.length}</strong>
          <span>{filtered.length === 1 ? "case" : "cases"}</span>
        </div>
        <div className="case-list" role="list">
          {filtered.map((item) => (
            <button
              className={selected?.id === item.id ? "case-card selected" : "case-card"}
              key={item.id}
              onClick={() => chooseCase(item)}
              role="listitem"
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
            </button>
          ))}
        </div>
      </aside>
      <div className="map-region">
        <div ref={mapNode} className="map" aria-label="Map of Detroit BZA cases" />
        <div className="map-note">
          Color identifies one request type. Size indicates hearing appearances.
          Road context from OpenStreetMap.
        </div>
        {selected && (
          <article className="case-detail">
            <button
              className="detail-close"
              onClick={() => setSelected(null)}
              aria-label="Close case details"
            >×</button>
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
          </article>
        )}
      </div>
    </section>
  );
}
