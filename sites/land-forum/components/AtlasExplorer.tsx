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
  const [mapReady, setMapReady] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All requests");
  const [outcome, setOutcome] = useState("All outcomes");
  const [year, setYear] = useState("All years");
  const [selected, setSelected] = useState<CaseRecord | null>(null);

  useEffect(() => {
    fetch("/data/bza-cases.json")
      .then((response) => response.json())
      .then(setCases);
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
        attributionControl: true,
      });
      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        {
          maxZoom: 19,
          attribution:
            "&copy; OpenStreetMap contributors &copy; CARTO",
        },
      ).addTo(map);
      map.fitBounds(
        [[42.245, -83.305], [42.46, -82.91]],
        { padding: [24, 24] },
      );
      mapRef.current = map;
      setMapReady(true);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    let cancelled = false;
    import("leaflet").then((L) => {
      if (cancelled || !mapRef.current) return;
      layerRef.current.forEach((layer) => layer.remove());
      layerRef.current = filtered.map((item) => {
        const marker = L.circleMarker([item.lat, item.lon], {
          radius: 5 + Math.sqrt(item.appearances) * 2,
          color: "#fffaf0",
          weight: 2,
          fillColor: CATEGORY_COLORS[item.categoryLabel] || "#73777d",
          fillOpacity: 0.88,
        });
        marker
          .bindTooltip(
            `<strong>${item.caseNumber}</strong><br>${item.address}`,
            { direction: "top" },
          )
          .on("click", () => setSelected(item))
          .addTo(mapRef.current!);
        return marker;
      });
    });
    return () => { cancelled = true; };
  }, [filtered, mapReady]);

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
