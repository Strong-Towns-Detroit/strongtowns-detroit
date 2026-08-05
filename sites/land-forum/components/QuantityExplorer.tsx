"use client";

import { useCallback, useMemo, useState } from "react";
import MapCanvas, { type PickedFeature } from "../lib/atlas/MapCanvas";
import { formatMeasure } from "../lib/atlas/specs/parcel-rule";
import {
  quantityCoverage,
  quantitySpec,
  type QuantityMapConfig,
  type QuantitySummary,
} from "../lib/atlas/specs/quantity";

export default function QuantityExplorer({
  config,
  summary,
}: {
  config: QuantityMapConfig;
  summary: QuantitySummary;
}) {
  const spec = useMemo(() => quantitySpec(config), [config]);
  const [picked, setPicked] = useState<PickedFeature | null>(null);
  const handlePick = useCallback((f: PickedFeature | null) => setPicked(f), []);
  const selectedId = picked
    ? String(picked.properties[spec.inspect!.idField] ?? "")
    : null;

  return (
    <div className="pub-body">
      <div className="pub-panel">
        <div className="pub-stat">
          <b>{Math.round(summary.topTenPercentLandValueShare * 100)}%</b>
          <span>{config.metricLabel.join(" ")}</span>
          <small>{config.metricNote.join(" ")}</small>
        </div>

        <div className="pub-legend">
          <h2>What the colours mean</h2>
          <ul>
            {spec.legend.map((entry) => (
              <li key={entry.label}>
                <i style={{ background: entry.color }} aria-hidden="true" />
                <span>{entry.label}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="pub-inspect">
          {picked ? (
            <>
              <h2>
                {String(
                  picked.properties[spec.inspect!.titleField] ??
                    "Address not recorded",
                )}
              </h2>
              <dl>
                {spec.inspect!.fields.map((field) => (
                  <div key={field.field}>
                    <dt>{field.label}</dt>
                    <dd>
                      {formatMeasure(
                        picked.properties[field.field],
                        field.format,
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="pub-empty" style={{ marginTop: 16 }}>
                {config.aside.lines.join(" ")}
              </p>
            </>
          ) : (
            <p className="pub-empty">
              Select a parcel on the map to see its assessed value per acre.
              <br />
              <br />
              {quantityCoverage(summary)}
            </p>
          )}
        </div>
      </div>

      <div className="pub-map-region">
        <MapCanvas spec={spec} onPick={handlePick} selectedId={selectedId} />
      </div>
    </div>
  );
}
