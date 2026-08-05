"use client";

/**
 * The interactive view for any parcel dimensional standard.
 *
 * Written once. Minimum lot area and minimum lot width differ only by their
 * config object and which tile column they read.
 */

import { useCallback, useMemo, useState } from "react";
import MapCanvas, { type PickedFeature } from "../lib/atlas/MapCanvas";
import {
  formatMeasure,
  parcelRuleSpec,
  ruleAccounting,
  type ParcelRuleConfig,
  type ParcelRuleSummary,
} from "../lib/atlas/specs/parcel-rule";

export default function ParcelRuleExplorer({
  config,
  summary,
}: {
  config: ParcelRuleConfig;
  summary: ParcelRuleSummary;
}) {
  const spec = useMemo(() => parcelRuleSpec(config), [config]);
  const [picked, setPicked] = useState<PickedFeature | null>(null);

  const handlePick = useCallback((feature: PickedFeature | null) => {
    setPicked(feature);
  }, []);

  const selectedId = picked
    ? String(picked.properties[spec.inspect!.idField] ?? "")
    : null;

  return (
    <div className="pub-body">
      <div className="pub-panel">
        <div className="pub-stat">
          <b>{Math.round(summary.belowMinimumShare * 100)}%</b>
          <span>{config.metricLabel.join(" ")}</span>
          <small>
            {summary.belowMinimumParcels.toLocaleString()} of{" "}
            {summary.evaluatedParcels.toLocaleString()} evaluated parcels.{" "}
            {summary.bzaCases} BZA case histories sought{" "}
            {config.bzaHistoryLabel} relief.
          </small>
        </div>

        <div className="pub-legend">
          <h2>What the colours mean</h2>
          <ul>
            {spec.legend.map((entry) => (
              <li key={entry.label}>
                <i style={{ background: entry.color }} aria-hidden="true" />
                <span>
                  {entry.label}
                  {entry.note && <em>{entry.note}</em>}
                </span>
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
                A geometric result is not a finding of illegality. Existing
                buildings may be lawful nonconformities, hold a variance, or
                rely on lot-of-record protection.
              </p>
            </>
          ) : (
            <p className="pub-empty">
              Select a parcel on the map to see its recorded values and how they
              compare with the minimum.
              <br />
              <br />
              {ruleAccounting(config, summary)}
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
