"use client";

/**
 * The frozen board for any parcel dimensional standard.
 *
 * Same MapCanvas and same MapSpec as the interactive route — only the frame and
 * the interaction differ. Neither can show a different classification, palette,
 * or figure than the other, because there is nothing to keep in sync.
 */

import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import MapCanvas from "../lib/atlas/MapCanvas";
import ExhibitFrame from "../lib/atlas/ExhibitFrame";
import { exhibit } from "../lib/tokens";
import {
  parcelRuleSpec,
  ruleAccounting,
  ruleMetric,
  type ParcelRuleConfig,
  type ParcelRuleSummary,
} from "../lib/atlas/specs/parcel-rule";

export default function ParcelRulePoster({
  config,
  summary,
}: {
  config: ParcelRuleConfig;
  summary: ParcelRuleSummary;
}) {
  const spec = useMemo(() => parcelRuleSpec(config), [config]);
  const params = useSearchParams();
  // ?scale=0.5 previews the board on screen; the exporter captures at 1.
  const scale = Number(params.get("scale") ?? "1") || 1;

  return (
    <ExhibitFrame
      title={spec.title}
      subtitle={spec.subtitle}
      metric={ruleMetric(config, summary)}
      legend={spec.legend}
      legendColumns={[67, 345, 565]}
      sources={[
        spec.sources[0],
        `${ruleAccounting(config, summary)} ${spec.sources[1]}`,
      ]}
      scale={scale}
      aside={
        <div className="ex-aside">
          <p className="ex-section-title">
            {summary.bzaCases} {config.bzaLabel} cases at the BZA
          </p>
          <p className="ex-source-line">
            From {config.bzaHistoryLabel} histories
          </p>
          <p className="ex-source-line" style={{ marginTop: 0 }}>
            identified in the 2019–2026 BZA minutes
          </p>
        </div>
      }
    >
      <MapCanvas
        spec={spec}
        frozen
        width={exhibit.map.width}
        height={exhibit.map.height}
      />
    </ExhibitFrame>
  );
}
