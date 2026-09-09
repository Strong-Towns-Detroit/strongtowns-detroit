"use client";
import { useEffect, useState } from "react";
import { fetchJson } from "../lib/atlas/data";

type Provenance = { inputs: Record<string, { snapshot_id: string; manifest_sha256: string; created_at: string }> };
export default function DataSources({ kind }: { kind: "bza" | "parcel" }) {
  const [metadata, setMetadata] = useState<Provenance | null>(null);
  const [failed, setFailed] = useState(false);
  const path = kind === "bza" ? "/data/bza-provenance.json" : "/data/zoning/parcel-provenance.json";
  useEffect(() => {
    const controller = new AbortController();
    fetchJson(path, controller.signal).then((value) => {
      const data = value as Provenance;
      if (!data?.inputs || typeof data.inputs !== "object" || !Object.values(data.inputs).every((entry) =>
        entry && typeof entry.snapshot_id === "string" && typeof entry.manifest_sha256 === "string" && typeof entry.created_at === "string")) throw new Error("Invalid source metadata");
      if (!controller.signal.aborted) setMetadata(data);
    }).catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, [path]);
  return <details className="data-sources">
    <summary>Data sources and downloads</summary>
    {failed && <p>Source metadata is unavailable for this build.</p>}
    {!failed && !metadata && <p>Loading source metadata…</p>}
    {metadata && <>
      <p>Snapshot dates identify the data used for this publication; they are not necessarily the dates of the underlying observations.</p>
      <ul>{Object.entries(metadata.inputs).map(([name, entry]) => <li key={name}>
        <b>{name}</b><br />Snapshot recorded {entry.created_at.slice(0, 10)}<br /><small>{entry.snapshot_id}</small>
      </li>)}</ul>
      <a href={path} download>Download source manifest</a>
    </>}
    <p><a href={kind === "bza" ? "/data/bza-cases.json" : "/data/zoning/parcel-rules.json"} download>
      Download {kind === "bza" ? "case records" : "publication figures"} (JSON)
    </a></p>
  </details>;
}
