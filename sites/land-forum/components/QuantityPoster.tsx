"use client";

import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import MapCanvas from "../lib/atlas/MapCanvas";
import ExhibitFrame from "../lib/atlas/ExhibitFrame";
import { exhibit } from "../lib/tokens";
import {
  quantityCoverage,
  quantityMetric,
  quantitySpec,
  type QuantityMapConfig,
  type QuantitySummary,
} from "../lib/atlas/specs/quantity";

export default function QuantityPoster({
  config,
  summary,
}: {
  config: QuantityMapConfig;
  summary: QuantitySummary;
}) {
  const spec = useMemo(() => quantitySpec(config), [config]);
  const params = useSearchParams();
  const scale = Number(params.get("scale") ?? "1") || 1;

  return (
    <ExhibitFrame
      title={spec.title}
      subtitle={spec.subtitle}
      metric={quantityMetric(config, summary)}
      legend={spec.legend}
      legendRows={config.legendRows}
      sources={[quantityCoverage(summary), ...config.sources]}
      scale={scale}
      aside={
        <div className="ex-aside">
          <p className="ex-section-title">{config.aside.title}</p>
          {config.aside.lines.map((line) => (
            <p className="ex-note" key={line}>
              {line}
            </p>
          ))}
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
